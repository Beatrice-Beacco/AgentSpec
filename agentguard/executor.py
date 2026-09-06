"""The walking skeleton: Cedar makes the decision (plan.md S1.7).

`CedarControlledAgentExecutor` overrides exactly one method of AgentSpec's
`ControlledAgentExecutor` -- `validate_and_enforce` -- and replaces the
rule-by-rule loop with the pipeline from thesis §C.1:

    sensors  ->  request  ->  Cedar  ->  advice  ->  enforcement.py

Everything else (the ReAct loop, the enforcement classes, the observation text
fed back to the agent) is reused unchanged, so a verdict difference between the
two engines is a difference in *deciding*, not in plumbing. That is what makes
the S1.7 parity test meaningful.

Two things are deliberately not general yet:

  * one *active* sensor. All 36 are registered (agentguard/sensors.py, S2.1);
    this engine still evaluates one, because core.cedar still reads one flag.
    S2.3 makes the selection domain-aware.
  * one hard-coded principal. The Session entity that carries taints across
    steps -- the actual thesis contribution -- is S4.2.

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
from agentguard import sensors as sensor_registry
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
# The registry itself is agentguard/sensors.py (S2.1). What lives here is the
# *selection*: which of the 36 this engine actually runs.

#: The sensors this engine materialises. Still one, because core.cedar still
#: reads one flag -- widening it would pay for 35 evaluations no policy asks
#: about. S2.3 replaces the hard-coded tuple with a domain-aware selection,
#: which is the point of Sensor.domain: six of the 36 raise rather than return
#: False when run on a code agent's trace, because they are embodied sensors
#: expecting embodied observations.
ACTIVE_SENSORS = ("destuctive_os_inst",)


def sensors():
    """The Sensor objects this engine materialises, by name.

    Resolved through the registry rather than indexing predicate_table
    directly, so a typo is a KeyError at construction naming what is available
    -- not, as in AgentSpec, a KeyError mid-run (S0.12's `is_malware`).
    """
    return {name: sensor_registry.get(name) for name in ACTIVE_SENSORS}


def run_sensors(state: RuleState) -> List[str]:
    """Evaluate every active sensor over the proposed action; return what fired.

    This is the impure half of the architecture and the only place arbitrary
    Python runs. Cedar expressions are pure and total, so a regex like
    `destuctive_os_inst` can never live inside a policy -- it runs here and
    arrives as a member of `context.flags`.

    Exceptions are *not* caught; see sensors.evaluate for why.
    """
    tool_input = state.action.input if state.action else None
    if tool_input is None:
        # AgentFinish carries no tool input. The predicates all index into a
        # string, so there is nothing to sense (and `action finish` is not in
        # the schema until S2.7).
        return []
    text = tool_input if isinstance(tool_input, str) else str(tool_input)
    fired = []
    for sensor in sensors().values():
        if sensor_registry.evaluate(sensor, state.user_input, text,
                                    state.intermediate_steps):
            fired.extend(sensor.flags)
    return sorted(set(fired))


# ---------------------------------------------------------------- advice
# S2.4 moves this to agentguard/advice.py, together with the `substitute`
# rule (a rewrite may only apply when it is the unique determining policy).

#: Enforcement outcomes, most restrictive first (thesis §C.4).
ADVICE_LATTICE = ["stop", "user_inspection", "llm_self_reflect", "skip", "allow"]

#: Advice -> the key in AgentSpec's own ENFORCEMENT_TO_CLASS. The lattice names
#: were chosen to line up with it, so this mapping is almost an identity; the
#: one real entry is `allow`, which AgentSpec spells `none`.
ADVICE_TO_ENFORCEMENT = {
    "allow": "none",
    "skip": "skip",
    "llm_self_reflect": "llm_self_reflect",
    "user_inspection": "user_inspection",
    "stop": "stop",
}

#: What an unannotated `forbid` means: the safe end of the lattice.
DEFAULT_ADVICE = "stop"


def join(advice) -> str:
    """The most restrictive of several advice values.

    The join exists because Cedar can return Deny from several policies at once
    and does *not* list them in source order (docs/spikes.md S1.2 saw
    ['policy2', 'policy1']). Anything that read "the first determining policy"
    would be reading an unspecified ordering; the join makes order irrelevant by
    construction. That is thesis claim M2, and S2.8 turns it into a property test.
    """
    return min(advice, key=ADVICE_LATTICE.index)


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

    schema = Schema.from_str(read(schema_path))
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
                        schema=schema, annotations=annotations)


# ---------------------------------------------------------------- request
# S2.3 moves this to agentguard/request.py, where the entity store also grows
# a Session (S4.2) and the context grows targets/risk/step (S2.2).


def _literal(value: str) -> str:
    """Escape a string for use inside a Cedar entity uid.

    The tool name reaches us from the model's own output, so it is
    attacker-influenced whenever the task prompt is. Interpolating it raw into
    `Tool::"..."` would let a crafted name close the quote and change which
    policies apply. Cedar would most likely reject the result -- a parse failure
    is NoDecision, which we fail closed on -- but relying on a parser to catch
    an injection is not a control.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_request(tool_name: str, flags) -> Dict[str, Any]:
    return {
        "principal": f'{NAMESPACE}::Agent::"{AGENT_ID}"',
        "action": f'{NAMESPACE}::Action::"invoke"',
        "resource": f'{NAMESPACE}::Tool::"{_literal(tool_name)}"',
        "context": {"flags": list(flags)},
    }


def build_entities(tool_name: str) -> List[Dict[str, Any]]:
    """The entity store for one decision.

    `kind` and `reversible` are placeholders: no policy in core.cedar reads
    them, and inventing a plausible value per tool would be fabricating the tool
    registry that S2.1 builds properly. `reversible: false` is the conservative
    default -- assume an effect cannot be undone until something says otherwise.
    """
    return [
        {"uid": {"type": f"{NAMESPACE}::Agent", "id": AGENT_ID},
         "attrs": {"framework": FRAMEWORK}, "parents": []},
        {"uid": {"type": f"{NAMESPACE}::Tool", "id": tool_name},
         "attrs": {"kind": "unknown", "reversible": False}, "parents": []},
    ]


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


def _describe(bundle: PolicyBundle, policy_ids, advice: str, errors) -> str:
    lines = []
    for pid in policy_ids:
        source = bundle.source_for(pid)
        lines.append(f"  @{bundle.name_for(pid)} -> {bundle.advice_for(pid)}"
                     + (f"  [{source}]" if source else ""))
    for message in errors:
        lines.append(f"  engine error: {message}")
    return f"cedar policy set (advice: {advice})\n" + "\n".join(lines)


def decide(bundle: PolicyBundle, state: RuleState) -> CedarVerdict:
    """Run the sensors, ask Cedar, resolve one enforcement outcome."""
    with profiling.phase("predicate_eval"):
        flags = run_sensors(state)

    tool_name = state.action.name
    # S2.9 adds a `cedar_decide` phase to src/profiling.py. Until then the
    # decision itself is unmeasured, so guard_ms under-reports for this engine
    # -- don't quote a Cedar guard total from a profile run before S2.9.
    result = is_authorized(build_request(tool_name, flags), bundle.policy_set,
                           build_entities(tool_name), bundle.schema)

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
                            errors=errors,
                            raw=_describe(bundle, policy_ids, advice, errors))

    if result.decision == Decision.Allow:
        return CedarVerdict(id="__allow__", raw="", advice="allow",
                            decision="Allow", policy_ids=policy_ids)

    advice = join([bundle.advice_for(pid) for pid in policy_ids] or [DEFAULT_ADVICE])
    determining = [pid for pid in policy_ids if bundle.advice_for(pid) == advice]
    return CedarVerdict(
        id=", ".join(bundle.name_for(pid) for pid in determining) or "__deny__",
        advice=advice, decision="Deny", policy_ids=policy_ids,
        raw=_describe(bundle, policy_ids, advice, ()),
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
