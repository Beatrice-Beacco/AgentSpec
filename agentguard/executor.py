"""The walking skeleton: Cedar makes the decision (plan.md S1.7).

`CedarControlledAgentExecutor` overrides exactly one method of AgentSpec's
`ControlledAgentExecutor` -- `validate_and_enforce` -- and replaces the
rule-by-rule loop with the pipeline from thesis §C.1:

    sensors  ->  request  ->  Cedar  ->  advice  ->  enforcement.py

Everything else (the ReAct loop, the enforcement classes, the observation text
fed back to the agent) is reused unchanged, so a verdict difference between the
two engines is a difference in *deciding*, not in plumbing. That is what makes
the S1.7 parity test meaningful.

Sensors, request building and the entity store live in agentguard/request.py
(S2.3); the registry they are selected from is agentguard/sensors.py (S2.1).
What is left here is loading the policy set, asking Cedar, and mapping the
answer onto AgentSpec's enforcement classes.

One thing is deliberately not general yet: a single hard-coded principal. The
Session entity that carries taints across steps -- the actual thesis
contribution -- is S4.2.

Run the suite through it with:

    AGENTGUARD=cedar .venv/bin/pytest -q tests/test_cedar_executor.py
"""
import functools
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from cedarpy import (Decision, PolicySet, Schema, is_authorized,
                     policies_to_json_str, validate_policies)

import agentguard
import profiling
from agent import Action
from controlled_agent_excector import ControlledAgentExecutor
from enforcement import ENFORCEMENT_TO_CLASS, EnforceResult
from agentguard import advice as ag_advice
from agentguard import request as ag_request
from agentguard import schema as ag_schema
from state import RuleState

NAMESPACE = "AgentGuard"
AGENT_ID = "agent"
FRAMEWORK = "langchain"


class PolicyError(RuntimeError):
    """The policy set could not be loaded or does not validate.

    Raised at agent construction, never mid-run. This is the half of RQ6 the
    Cedar engine gets for free: `tests/test_fail_open.py` records four ways a
    malformed AgentSpec rule gets past loading and surfaces later or not at all.
    S2.5 widens this to the whole engine and flips those xfails.
    """


# ---------------------------------------------------------------- sensors
# Selection and evaluation moved to agentguard/request.py (S2.3). The engine no
# longer names sensors at all: it asks for a domain, and the registry's metadata
# decides what can safely run there.

#: Which agent binding this executor guards. Only `code` is wired up; an
#: embodied or shell binding sets its own. Nothing infers it from the action.
DOMAIN = ag_request.DEFAULT_DOMAIN


# ---------------------------------------------------------------- advice
# The lattice, the join and the substitution rule live in agentguard/advice.py
# (S2.4). What stays here is the map onto AgentSpec's own enforcement classes,
# which S2.6 moves to agentguard/enforcer.py.

#: Advice -> the key in AgentSpec's ENFORCEMENT_TO_CLASS. The lattice names were
#: chosen to line up with it, so this is almost an identity; the one real entry
#: is `allow`, which AgentSpec spells `none`. `substitute` has no entry: the
#: baseline's InvokeAction is unregistered and a no-op (docs/findings.md D-5),
#: so S2.6 has to implement the rewrite rather than delegate it.
ADVICE_TO_ENFORCEMENT = {
    ag_advice.ALLOW: "none",
    ag_advice.SKIP: "skip",
    ag_advice.LLM_SELF_REFLECT: "llm_self_reflect",
    ag_advice.USER_INSPECTION: "user_inspection",
    ag_advice.STOP: "stop",
}

#: Re-exported so callers do not reach past the engine for the common cases.
DEFAULT_ADVICE = ag_advice.DEFAULT
ADVICE_LATTICE = list(ag_advice.LATTICE)
join = ag_advice.join


# ----------------------------------------------------------- policy bundle
# S2.5 moves this to agentguard/engine.py.


@dataclass(frozen=True)
class PolicyBundle:
    """Everything loaded from `policies/`, parsed exactly once.

    S1.4 measured the cost of not doing this: passing policy *text* to every
    `is_authorized` call is 2x slower than passing a pre-parsed `PolicySet`
    (0.1196 ms vs 0.0579 ms). It is also the mistake AgentSpec makes -- 77.6% of
    its guard time is re-parsing rule text on every action (S0.11) -- so making
    it here would throw away the clearest RQ5 result available.
    """
    text: str
    policy_set: Any
    schema: Any
    #: Which shape context.flags takes, read out of the generated schema itself
    #: (S2.2) so the request builder cannot disagree with the type it is
    #: checked against.
    flags_variant: str = ag_schema.DEFAULT_VARIANT
    annotations: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def advice_for(self, policy_id: str) -> str:
        return self.annotations.get(policy_id, {}).get("advice", DEFAULT_ADVICE)

    def name_for(self, policy_id: str) -> str:
        return self.annotations.get(policy_id, {}).get("id", policy_id)

    def source_for(self, policy_id: str) -> Optional[str]:
        return self.annotations.get(policy_id, {}).get("source")


@functools.lru_cache(maxsize=None)
def load_bundle(policy_dir: Optional[str] = None) -> PolicyBundle:
    """Load, validate and parse the policy set. Cached; call `.cache_clear()` to reload.

    Validation happens here rather than at first decision on purpose: a policy
    set that does not type-check must stop the agent from *starting*, not
    produce a surprise halfway through a run.
    """
    policy_dir = policy_dir or agentguard.POLICY_DIR
    schema_path = os.path.join(policy_dir, "schema.cedarschema")
    policy_paths = sorted(
        os.path.join(policy_dir, name)
        for name in os.listdir(policy_dir) if name.endswith(".cedar")
    )
    if not policy_paths:
        raise PolicyError(f"no .cedar policy files in {policy_dir}")

    def read(path):
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    schema_text = read(schema_path)
    schema = Schema.from_str(schema_text)
    # Read the flags variant out of the schema itself rather than configuring it
    # separately, so the request builder and the type it is checked against
    # cannot drift apart (S2.2).
    flags_variant = ag_schema.variant_of(schema_text)
    text = "\n".join(read(path) for path in policy_paths)

    result = validate_policies(text, schema)
    if not result.validation_passed:
        detail = "\n  ".join(str(e).split("] ", 1)[-1] for e in result.errors)
        raise PolicyError(f"policy set does not validate against {schema_path}:\n  {detail}")

    # Annotations come from cedarpy's own parser, keyed by the same synthetic
    # ids diagnostics.reasons returns, so the join at decision time is direct
    # (docs/spikes.md S1.2 -- id_annotations_by_reason carries only @id).
    parsed = json.loads(policies_to_json_str(text))
    annotations = {pid: body.get("annotations", {})
                   for pid, body in parsed["staticPolicies"].items()}

    return PolicyBundle(text=text, policy_set=PolicySet.from_str(text),
                        schema=schema, flags_variant=flags_variant,
                        annotations=annotations)


# --------------------------------------------------------------- decision


@dataclass(frozen=True)
class CedarVerdict:
    """What the legacy engine calls "the rule that fired".

    `id` and `raw` exist because ControlledAgentExecutor._iter_next_step reads
    them off whatever validate_and_enforce returns -- `raw` ends up in the text
    the agent is shown when its action is stopped or skipped. Keeping the same
    duck type means the executor's own code needs no changes at all.
    """
    id: str
    raw: str
    advice: str
    decision: str
    policy_ids: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    #: What materialisation produced, kept so the bench and the tests can see
    #: the evidence a decision was made on rather than re-deriving it.
    materialisation: Optional[ag_request.Materialisation] = None
    #: How the determining policies were reduced to one outcome (S2.4). Carries
    #: the substitution, and the note when the outcome was not simply the join.
    resolution: Optional[ag_advice.Resolution] = None


def _describe(bundle: PolicyBundle, policy_ids, advice: str, errors) -> str:
    lines = []
    for pid in policy_ids:
        source = bundle.source_for(pid)
        lines.append(f"  @{bundle.name_for(pid)} -> {bundle.advice_for(pid)}"
                     + (f"  [{source}]" if source else ""))
    for message in errors:
        lines.append(f"  engine error: {message}")
    return f"cedar policy set (advice: {advice})\n" + "\n".join(lines)


def decide(bundle: PolicyBundle, state: RuleState,
           domain: str = None) -> CedarVerdict:
    """Materialise, ask Cedar, resolve one enforcement outcome."""
    with profiling.phase("predicate_eval"):
        material = ag_request.materialise(state, bundle.flags_variant,
                                          domain or DOMAIN)

    # A sensor that raised means we do not know what the action is doing.
    # Deciding anyway would be deciding on evidence we failed to gather, and
    # the missing flag reads to Cedar as "not evaluated" -- so any policy keyed
    # on it silently cannot fire. Stop instead, before asking.
    if material.errors:
        messages = tuple(str(failure) for failure in material.errors)
        return CedarVerdict(id="__sensor_error__", advice=DEFAULT_ADVICE,
                            decision="NotEvaluated", errors=messages,
                            materialisation=material,
                            raw=_describe(bundle, (), DEFAULT_ADVICE, messages))

    # S2.9 adds a `cedar_decide` phase to src/profiling.py. Until then the
    # decision itself is unmeasured, so guard_ms under-reports for this engine
    # -- don't quote a Cedar guard total from a profile run before S2.9.
    result = is_authorized(material.request, bundle.policy_set,
                           material.entities, bundle.schema)

    errors = tuple(str(e) for e in result.diagnostics.errors)
    policy_ids = tuple(result.diagnostics.reasons)

    # Fail closed. Cedar returns NoDecision -- not an exception -- when it
    # cannot evaluate the request at all (a malformed entity store does this).
    # Treating "not Deny" as permission would turn an engine fault into a
    # silent allow, which is the failure mode this whole project is about.
    if errors or result.decision not in (Decision.Allow, Decision.Deny):
        advice = DEFAULT_ADVICE
        return CedarVerdict(id="__engine_error__", advice=advice,
                            decision=str(result.decision), policy_ids=policy_ids,
                            errors=errors, materialisation=material,
                            raw=_describe(bundle, policy_ids, advice, errors))

    if result.decision == Decision.Allow:
        return CedarVerdict(id="__allow__", raw="", advice=ag_advice.ALLOW,
                            decision="Allow", policy_ids=policy_ids,
                            materialisation=material,
                            resolution=ag_advice.resolve(True, ()))

    resolution = ag_advice.resolve(
        allow=False,
        contributions=[ag_advice.contribution(pid, bundle.annotations.get(pid, {}))
                       for pid in policy_ids],
    )
    # Name the policies that actually carried the winning outcome, not every one
    # that denied -- that is what a reader wants to see in "stopped by ...".
    determining = [c.policy for c in resolution.contributing
                   if c.advice == resolution.advice] or [c.policy for c in
                                                         resolution.contributing]
    return CedarVerdict(
        id=", ".join(determining) or "__deny__",
        advice=resolution.advice, decision="Deny", policy_ids=policy_ids,
        materialisation=material, resolution=resolution,
        raw=_describe(bundle, policy_ids, resolution.advice, ()) +
            (f"\n  note: {resolution.note}" if resolution.note else ""),
    )


# --------------------------------------------------------------- executor


class CedarControlledAgentExecutor(ControlledAgentExecutor):
    """ControlledAgentExecutor with the rule loop replaced by a Cedar decision."""

    @classmethod
    def from_agent_and_tools(cls, agent, tools, rules, callbacks=None, **kwargs):
        # Load eagerly: a policy set that does not validate must stop the agent
        # being built, not surface on the first dangerous action.
        load_bundle()
        return super().from_agent_and_tools(agent, tools, rules, callbacks, **kwargs)

    def validate_and_enforce(self, action: Action, state: RuleState):
        """Return (what fired, the action to take) -- same contract as the legacy engine."""
        if action.is_finish():
            # `action finish` is not in the schema until S2.7, and the sensors
            # have no tool input to look at. The legacy engine would still run
            # `trigger finish` rules here; that difference is S2.7's to close.
            return None, action

        profiling.count_rule()
        verdict = decide(load_bundle(), state)
        if verdict.advice == "allow":
            return None, action

        enforcement = ENFORCEMENT_TO_CLASS[ADVICE_TO_ENFORCEMENT[verdict.advice]]
        with profiling.phase("enforcement"):
            outcome, next_action = enforcement(state=state).apply(action)

        if outcome == EnforceResult.CONTINUE:
            # `user_inspection` where the user approved, or `none`.
            return None, action
        if outcome == EnforceResult.SKIP:
            return verdict, Action.get_skip()
        if outcome == EnforceResult.STOP:
            # Phrased exactly as the legacy executor phrases it, so the text the
            # agent and the tests see is identical across engines.
            reason = f"action stopped by {verdict.raw}"
            return verdict, Action.get_finish(reason, reason)
        if outcome == EnforceResult.SELF_REFLECT:
            return self.validate_and_enforce(next_action, state)
        raise ValueError(f"unreachable enforcement result: {outcome}")
