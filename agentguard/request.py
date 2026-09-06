"""Materialisation: RuleState -> (Request, Entities)  (plan.md S2.3).

The boundary between the two halves of the architecture. Everything impure
happens here -- regexes over generated source, string indexing, whatever the
predicates feel like doing -- and what comes out is a plain JSON-shaped request
that Cedar can decide on with no I/O and no surprises.

    RuleState                       what the agent proposes to do
      |
      |  select()      which sensors apply to this domain
      |  run()         evaluate them; nothing here can raise into the caller
      |
      v
    Materialisation
      .request         principal / action / resource / context
      .entities        the entity store
      .evaluated       {flag: value} for every sensor that ran
      .errors          sensors that raised, if any -- the engine fails closed

Two decisions worth reading before changing anything here.

**Sensors are selected by domain, not by name.** S2.1 measured why: five of the
eleven embodied predicates *raise* rather than returning False when handed a
code agent's `intermediate_steps`, and the exception class is not even stable
(`is_unsafe_fillliquid` gives AttributeError on an input with spaces and
IndexError on one without). "Catch the known exception" was therefore never
available. Not running them is, and `Sensor.domain` is exactly that selector.
Across 10 varied inputs and 3 history shapes, 0 of the 25 code sensors raise.

**A sensor that raises does not silently vanish.** It is recorded in `.errors`
and the flag is left *absent* from the record, which under the S2.2 schema means
"nobody looked" rather than "we checked and it is fine". The engine turns any
error into a `stop`. That decision is deliberately made in Python rather than
exposed to policy: a broken sensor is an infrastructure fault, and a policy set
that forgot to handle it would fail open -- which is the whole failure class
this project exists to remove.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import agentguard  # noqa: F401  -- puts src/ on sys.path

from agentguard import schema as ag_schema
from agentguard import sensors as sensor_registry
from state import RuleState

NAMESPACE = "AgentGuard"
AGENT_ID = "agent"
FRAMEWORK = "langchain"

#: The only binding wired up. An embodied or shell agent sets its own domain;
#: nothing infers it from the action, because the domain is a property of how
#: the guard was configured and not something to sniff at runtime.
DEFAULT_DOMAIN = sensor_registry.CODE


@dataclass(frozen=True)
class SensorFailure:
    """A sensor that raised. Kept, not swallowed."""
    sensor: str
    error: str

    def __str__(self):
        return f"{self.sensor}: {self.error}"


@dataclass(frozen=True)
class Materialisation:
    """Everything one decision needs, and the record of how it was obtained."""
    request: Dict[str, Any]
    entities: List[Dict[str, Any]]
    evaluated: Dict[str, bool] = field(default_factory=dict)
    errors: Tuple[SensorFailure, ...] = ()
    domain: str = DEFAULT_DOMAIN

    @property
    def fired(self) -> List[str]:
        """The flags that came back true, sorted. For display and the set variant."""
        return sorted(flag for flag, value in self.evaluated.items() if value)


# ------------------------------------------------------------------ sensors

def select(domain=DEFAULT_DOMAIN, names=None):
    """The sensors to run: a whole domain, or an explicit subset of it.

    Passing `names` is how a test or an experiment narrows the set. It still
    goes through the registry, so a typo is a KeyError here rather than a flag
    that silently never appears -- AgentSpec's equivalent lookup fails mid-run
    (S0.12's `is_malware`).
    """
    if names is not None:
        return tuple(sensor_registry.get(name) for name in names)
    return sensor_registry.by_domain(domain)


def run(state: RuleState, chosen) -> Tuple[Dict[str, bool], Tuple[SensorFailure, ...]]:
    """Evaluate the chosen sensors over the proposed action.

    Returns ({flag: value} for every sensor that completed, failures). A sensor
    that raises contributes no flag at all: under the record schema an absent
    flag means "not evaluated", which is the truth, whereas `false` would be a
    claim that the dangerous thing is not happening.

    Cheapest first, because `sensor_registry.by_domain` returns them that way
    and a `model`-cost sensor should never be paid for before an `input`-cost
    one has had its say.
    """
    tool_input = state.action.input if state.action else None
    if tool_input is None:
        # AgentFinish carries no tool input, and `action finish` is not in the
        # schema until S2.7. Nothing to sense.
        return {}, ()

    text = tool_input if isinstance(tool_input, str) else str(tool_input)
    evaluated: Dict[str, bool] = {}
    failures: List[SensorFailure] = []
    for sensor in chosen:
        try:
            value = sensor_registry.evaluate(sensor, state.user_input, text,
                                             state.intermediate_steps)
        except Exception as exc:                        # noqa: BLE001
            # Deliberately broad: these are third-party predicates and S2.1
            # showed the exception type is not even stable for a given sensor.
            failures.append(SensorFailure(sensor.name, f"{type(exc).__name__}: {exc}"))
            continue
        for flag in sensor.flags:
            evaluated[flag] = value
    return evaluated, tuple(failures)


# ------------------------------------------------------------------ request

def _literal(value: str) -> str:
    """Escape a string for use inside a Cedar entity uid.

    The tool name reaches us from the model's own output, so it is
    attacker-influenced whenever the task prompt is. Interpolating it raw into
    `Tool::"..."` would let a crafted name close the quote and change which
    policies apply. Cedar would most likely reject the result -- a parse failure
    is NoDecision, which the engine fails closed on -- but relying on a parser
    to catch an injection is not a control.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def context_flags(evaluated: Dict[str, bool], variant: str):
    """Shape the sensor results the way the schema on disk declares them.

    The variant comes from the generated schema (S2.2) rather than a setting of
    our own, so the request and the type it is checked against cannot disagree.

      record   {flag: bool} for every sensor that ran. Absent means not run,
               and Cedar makes a policy say which of the two it means.
      set      [flag, ...] for the ones that fired. Cannot express "ran and
               said no" at all -- which is the point of the comparison.
    """
    if variant == ag_schema.RECORD:
        return dict(sorted(evaluated.items()))
    if variant == ag_schema.SET:
        return sorted(flag for flag, value in evaluated.items() if value)
    raise ValueError(f"schema declares an unknown flags variant {variant!r}")


def build_request(tool_name: str, evaluated: Dict[str, bool],
                  variant: str = ag_schema.DEFAULT_VARIANT) -> Dict[str, Any]:
    return {
        "principal": f'{NAMESPACE}::Agent::"{AGENT_ID}"',
        "action": f'{NAMESPACE}::Action::"invoke"',
        "resource": f'{NAMESPACE}::Tool::"{_literal(tool_name)}"',
        "context": {"flags": context_flags(evaluated, variant)},
    }


def build_entities(tool_name: str) -> List[Dict[str, Any]]:
    """The entity store for one decision.

    `kind` and `reversible` are placeholders. No policy in core.cedar reads
    them, and inventing a plausible value per tool would be fabricating the tool
    registry S2.7 has to build properly. `reversible: false` is the conservative
    default -- assume an effect cannot be undone until something says otherwise.
    """
    return [
        {"uid": {"type": f"{NAMESPACE}::Agent", "id": AGENT_ID},
         "attrs": {"framework": FRAMEWORK}, "parents": []},
        {"uid": {"type": f"{NAMESPACE}::Tool", "id": tool_name},
         "attrs": {"kind": "unknown", "reversible": False}, "parents": []},
    ]


def materialise(state: RuleState,
                variant: str = ag_schema.DEFAULT_VARIANT,
                domain: str = DEFAULT_DOMAIN,
                names: Optional[Tuple[str, ...]] = None) -> Materialisation:
    """RuleState -> everything Cedar needs. The whole impure half, in one call."""
    evaluated, errors = run(state, select(domain, names))
    tool_name = state.action.name if state.action else ""
    return Materialisation(
        request=build_request(tool_name, evaluated, variant),
        entities=build_entities(tool_name),
        evaluated=evaluated,
        errors=errors,
        domain=domain,
    )
