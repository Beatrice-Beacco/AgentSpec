"""Load, validate, decide (plan.md S2.5).

The engine proper. `executor.py` is the LangChain binding around it; everything
about *deciding* lives here, and nothing here knows what LangChain is.

    load()      read policies/, check them, parse once. Refuses to return a
                usable engine if anything is wrong.
    decide()    materialise -> Cedar -> resolve one enforcement outcome.

**Refusing to start is the point of this module** (RQ6). AgentSpec accepts a
malformed rule at load and surfaces the problem later or never
(`tests/test_fail_open.py` records four distinct ways). Here, four classes of
mistake are load-time errors, and the agent does not start:

  1. the policy set does not type-check against the schema      Cedar's validator
  2. an annotation is not a real enforcement outcome            our lint
  3. a policy has no @id, so its decision is untraceable        our lint
  4. a policy reads a flag no active sensor can produce         our coverage check

(4) is the one neither Cedar nor AgentSpec can do, and it is the most useful.
Cedar checks that a referenced flag *exists in the schema*; it cannot know that
the engine will never evaluate the sensor behind it. Such a policy type-checks,
loads, and then silently never fires -- which is exactly the failure mode this
project exists to remove, reappearing one level up. A safety policy that cannot
fire is worse than no policy, because it looks like coverage.

Everything is parsed exactly once. S1.4 measured the alternative: passing policy
*text* to each `is_authorized` costs 2x, and it is the mistake AgentSpec makes on
every action (S0.11: 77.6% of its guard time is re-parsing rule text).
"""
import functools
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Optional, Tuple

from cedarpy import (Decision, PolicySet, Schema, is_authorized,
                     policies_to_json_str, validate_policies)

import agentguard
import profiling
from agentguard import advice as ag_advice
from agentguard import request as ag_request
from agentguard import schema as ag_schema
from agentguard import sensors as sensor_registry
from state import RuleState

SCHEMA_FILE = "schema.cedarschema"


class PolicyError(RuntimeError):
    """The policy set cannot be trusted, so the agent must not start.

    Raised from `load()`, never mid-run. Every message names the policy and says
    what to do about it: an engine that refuses to start is only an improvement
    on one that fails open if the refusal is actionable.
    """


# ---------------------------------------------------------- what a policy reads

#: The shape `context.flags` takes in cedarpy's policy JSON.
_CONTEXT_FLAGS = {".": {"left": {"Var": "context"}, "attr": "flags"}}


def referenced_flags(node) -> FrozenSet[str]:
    """Every flag name a policy's conditions mention.

    Walks the JSON Cedar itself produces rather than the policy text, so it sees
    what the evaluator sees -- the same reasoning as the annotation table in
    docs/spikes.md S1.2. Handles both schema variants:

        record   context.flags has X   and   context.flags.X
        set      context.flags.contains("X")
    """
    found = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("has", ".") and isinstance(value, dict):
                if value.get("left") == _CONTEXT_FLAGS and "attr" in value:
                    found.add(value["attr"])
            if key == "contains" and isinstance(value, dict):
                if value.get("left") == _CONTEXT_FLAGS:
                    literal = value.get("right", {})
                    if isinstance(literal, dict) and isinstance(
                            literal.get("Value"), str):
                        found.add(literal["Value"])
            found |= referenced_flags(value)
    elif isinstance(node, list):
        for item in node:
            found |= referenced_flags(item)
    return frozenset(found)


# ------------------------------------------------------------------- bundle


@dataclass(frozen=True)
class PolicyBundle:
    """Everything one engine needs, parsed and checked exactly once."""
    text: str
    policy_set: Any
    schema: Any
    #: Which shape context.flags takes, read out of the generated schema itself
    #: (S2.2) so the request builder cannot disagree with the type it is
    #: checked against.
    flags_variant: str = ag_schema.DEFAULT_VARIANT
    #: The domain whose sensors this engine will run. Part of the bundle because
    #: the coverage check is only meaningful against a specific one.
    domain: str = ag_request.DEFAULT_DOMAIN
    annotations: Dict[str, Dict[str, str]] = field(default_factory=dict)
    #: policy id -> the flags its conditions read.
    flags_read: Dict[str, FrozenSet[str]] = field(default_factory=dict)

    def advice_for(self, policy_id: str) -> str:
        return self.annotations.get(policy_id, {}).get("advice", ag_advice.DEFAULT)

    def name_for(self, policy_id: str) -> str:
        return self.annotations.get(policy_id, {}).get("id", policy_id)

    def source_for(self, policy_id: str) -> Optional[str]:
        return self.annotations.get(policy_id, {}).get("source")

    def contribution(self, policy_id: str) -> ag_advice.Contribution:
        return ag_advice.contribution(policy_id,
                                      self.annotations.get(policy_id, {}))


# ----------------------------------------------------------- startup checks


def annotation_errors(annotations) -> Tuple[str, ...]:
    """The lint from tools/validate_policies.py, enforced by the engine too.

    Until S2.5 the CLI validated strictly more than the engine did, so a policy
    set that had never been through `make validate` could load with a typo'd
    `@advice` and only misbehave at decision time. Checking here closes that:
    the gate is not something you have to remember to run.
    """
    errors = []
    for pid, anns in sorted(annotations.items()):
        name = anns.get("id", pid)
        if "id" not in anns:
            errors.append(f"{pid}: no @id -- its decisions cannot be traced to a rule")
        value = anns.get("advice")
        if value is not None and value not in ag_advice.VALUES:
            errors.append(f"{name}: @advice(\"{value}\") is not an enforcement "
                          f"outcome (expected one of {', '.join(ag_advice.VALUES)})")
        if value == ag_advice.SUBSTITUTE and not anns.get(ag_advice.TOOL_ANNOTATION):
            errors.append(f"{name}: @advice(\"{ag_advice.SUBSTITUTE}\") needs "
                          f"@{ag_advice.TOOL_ANNOTATION} naming the replacement tool")
    return tuple(errors)


def coverage_errors(flags_read, annotations, domain) -> Tuple[str, ...]:
    """Policies that read a flag no sensor in `domain` will ever produce.

    Cedar cannot catch this. It checks that a flag exists *in the schema*, and
    the schema declares all 36 registered sensors -- but the engine only runs
    the ones its domain can safely evaluate (S2.3). A policy keyed on any of the
    others type-checks, loads, and never fires.

    That is the same silent-never-fires failure AgentSpec has, arriving one
    level up, so it gets the same treatment: refuse to start.
    """
    available = {flag for sensor in ag_request.select(domain)
                 for flag in sensor.flags}
    errors = []
    for pid, flags in sorted(flags_read.items()):
        missing = sorted(set(flags) - available)
        if not missing:
            continue
        name = annotations.get(pid, {}).get("id", pid)
        detail = []
        for flag in missing:
            if flag in sensor_registry.SENSORS:
                other = sensor_registry.SENSORS[flag].domain
                detail.append(f"{flag} (domain {other}; this engine runs {domain})")
            else:
                detail.append(f"{flag} (no registered sensor sets it -- misspelled?)")
        errors.append(
            f"{name}: reads a flag that is never materialised, so the policy "
            f"can never fire -- " + "; ".join(detail))
    return tuple(errors)


# --------------------------------------------------------------------- load


@functools.lru_cache(maxsize=None)
def load(policy_dir: Optional[str] = None,
         domain: Optional[str] = None) -> PolicyBundle:
    """Load and check the policy set, or raise PolicyError. Cached.

    Call `load.cache_clear()` to force a reload.
    """
    policy_dir = policy_dir or agentguard.POLICY_DIR
    domain = domain or ag_request.DEFAULT_DOMAIN
    schema_path = os.path.join(policy_dir, SCHEMA_FILE)

    if not os.path.isdir(policy_dir):
        raise PolicyError(f"no policy directory at {policy_dir}")
    if not os.path.isfile(schema_path):
        raise PolicyError(f"no {SCHEMA_FILE} in {policy_dir} -- run `make schema`")

    policy_paths = sorted(
        os.path.join(policy_dir, name)
        for name in os.listdir(policy_dir) if name.endswith(".cedar")
    )
    if not policy_paths:
        raise PolicyError(
            f"no .cedar policy files in {policy_dir}. An engine with no policies "
            "would allow everything, which is not a state worth starting in.")

    def read(path):
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    schema_text = read(schema_path)
    try:
        schema = Schema.from_str(schema_text)
    except Exception as exc:                            # noqa: BLE001
        raise PolicyError(f"{schema_path} does not parse:\n  {exc}") from None
    flags_variant = ag_schema.variant_of(schema_text)

    text = "\n".join(read(path) for path in policy_paths)

    # 1. does it type-check?
    result = validate_policies(text, schema)
    if not result.validation_passed:
        detail = "\n  ".join(str(e).split("] ", 1)[-1] for e in result.errors)
        raise PolicyError(
            f"policy set does not validate against {schema_path}:\n  {detail}")

    # Annotations and conditions come from cedarpy's own parser, keyed by the
    # same synthetic ids diagnostics.reasons returns, so the joins at decision
    # time are direct (docs/spikes.md S1.2).
    parsed = json.loads(policies_to_json_str(text))["staticPolicies"]
    annotations = {pid: body.get("annotations", {}) for pid, body in parsed.items()}
    flags_read = {pid: referenced_flags(body.get("conditions", []))
                  for pid, body in parsed.items()}

    # 2/3. are the annotations meaningful?  4. can every policy actually fire?
    problems = (annotation_errors(annotations)
                + coverage_errors(flags_read, annotations, domain))
    if problems:
        raise PolicyError("policy set is not usable:\n  " + "\n  ".join(problems))

    return PolicyBundle(text=text, policy_set=PolicySet.from_str(text),
                        schema=schema, flags_variant=flags_variant, domain=domain,
                        annotations=annotations, flags_read=flags_read)


# ----------------------------------------------------------------- decision


@dataclass(frozen=True)
class Verdict:
    """One decision, and everything needed to explain or enforce it.

    `id` and `raw` exist because ControlledAgentExecutor._iter_next_step reads
    them off whatever validate_and_enforce returns -- `raw` ends up in the text
    the agent is shown when its action is stopped or skipped. Keeping the same
    duck type means the executor's own loop needs no changes at all.
    """
    id: str
    raw: str
    advice: str
    decision: str
    policy_ids: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    #: What materialisation produced -- the evidence the decision rests on.
    materialisation: Optional[ag_request.Materialisation] = None
    #: How the determining policies were reduced to one outcome (S2.4).
    resolution: Optional[ag_advice.Resolution] = None

    @property
    def allowed(self) -> bool:
        return self.advice == ag_advice.ALLOW


def describe(bundle: PolicyBundle, policy_ids, resolved: str, errors) -> str:
    lines = []
    for pid in policy_ids:
        source = bundle.source_for(pid)
        lines.append(f"  @{bundle.name_for(pid)} -> {bundle.advice_for(pid)}"
                     + (f"  [{source}]" if source else ""))
    for message in errors:
        lines.append(f"  engine error: {message}")
    return f"cedar policy set (advice: {resolved})\n" + "\n".join(lines)


def decide(bundle: PolicyBundle, state: RuleState,
           domain: Optional[str] = None) -> Verdict:
    """Materialise, ask Cedar, resolve one enforcement outcome."""
    with profiling.phase("predicate_eval"):
        material = ag_request.materialise(state, bundle.flags_variant,
                                          domain or bundle.domain)

    # A sensor that raised means we do not know what the action is doing.
    # Deciding anyway would be deciding on evidence we failed to gather, and the
    # missing flag reads to Cedar as "not evaluated" -- so any policy keyed on it
    # silently cannot fire. Stop instead, before asking.
    if material.errors:
        messages = tuple(str(failure) for failure in material.errors)
        return Verdict(id="__sensor_error__", advice=ag_advice.DEFAULT,
                       decision="NotEvaluated", errors=messages,
                       materialisation=material,
                       raw=describe(bundle, (), ag_advice.DEFAULT, messages))

    # The decision proper, timed apart from detection: RQ5's whole question is
    # which of the two costs anything (S2.9).
    with profiling.phase("cedar_decide"):
        result = is_authorized(material.request, bundle.policy_set,
                               material.entities, bundle.schema)

    errors = tuple(str(e) for e in result.diagnostics.errors)
    policy_ids = tuple(result.diagnostics.reasons)

    # Fail closed. Cedar returns NoDecision -- not an exception -- when it cannot
    # evaluate the request at all (a malformed entity store does this). Treating
    # "not Deny" as permission would turn an engine fault into a silent allow,
    # which is the failure mode this whole project is about.
    if errors or result.decision not in (Decision.Allow, Decision.Deny):
        return Verdict(id="__engine_error__", advice=ag_advice.DEFAULT,
                       decision=str(result.decision), policy_ids=policy_ids,
                       errors=errors, materialisation=material,
                       raw=describe(bundle, policy_ids, ag_advice.DEFAULT, errors))

    if result.decision == Decision.Allow:
        return Verdict(id="__allow__", raw="", advice=ag_advice.ALLOW,
                       decision="Allow", policy_ids=policy_ids,
                       materialisation=material,
                       resolution=ag_advice.resolve(True, ()))

    resolution = ag_advice.resolve(
        allow=False,
        contributions=[bundle.contribution(pid) for pid in policy_ids])
    # Name the policies that carried the winning outcome, not every one that
    # denied -- that is what a reader wants to see in "stopped by ...".
    determining = [c.policy for c in resolution.contributing
                   if c.advice == resolution.advice] \
        or [c.policy for c in resolution.contributing]
    return Verdict(
        id=", ".join(determining) or "__deny__",
        advice=resolution.advice, decision="Deny", policy_ids=policy_ids,
        materialisation=material, resolution=resolution,
        raw=describe(bundle, policy_ids, resolution.advice, ())
            + (f"\n  note: {resolution.note}" if resolution.note else ""),
    )
