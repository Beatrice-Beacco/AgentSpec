"""Advice -> enforcement (plan.md S2.6).

The last step of the pipeline: turn one resolved outcome into something the
agent loop can act on. The instruction for this step was "reuse them; don't
rewrite", and that is what happens -- the five lattice outcomes are applied by
AgentSpec's own classes in `src/enforcement.py`, unmodified.

Two of them need an adapter, and both adapters exist because of a defect in the
baseline rather than a difference of opinion:

`llm_self_reflect` returns the wrong type
-----------------------------------------
`LLMSelfReflect.apply` hands back the raw LangChain object `agent.plan()`
returned -- an `AgentAction` or `AgentFinish` -- not an AgentSpec `Action`. The
legacy executor then feeds it straight back into its own loop, whose first
statement is `action.is_finish()`, and the run dies with
`AttributeError: 'AgentFinish' object has no attribute 'is_finish'`. Verified end
to end; see docs/findings.md D-6. So `enforce llm_self_reflect` cannot complete
in AgentSpec at all. We wrap the return value instead of copying the bug.

`substitute` has nothing to reuse
---------------------------------
`InvokeAction` is defined but never registered in `ENFORCEMENT_TO_CLASS`, and is
a no-op that returns the original action even if it were (D-5). There is no
working implementation to delegate to, so this module provides one -- and it is
the only place where we add behaviour rather than route it.

A substitution is *guarded again* before it runs. It replaces a call the policy
set has just judged, with one the policy author wrote, so letting it through
unchecked would make `@substitute_tool` a way around the guard. Re-entering
costs a bounded recursion, which is why `MAX_REDIRECTS` exists.
"""
import json
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from agent import Action
from enforcement import ENFORCEMENT_TO_CLASS, EnforceResult

from agentguard import advice as ag_advice

#: Advice -> the key in AgentSpec's own ENFORCEMENT_TO_CLASS. The lattice names
#: were chosen to line up with it, so this is nearly an identity; the one real
#: entry is `allow`, which AgentSpec spells `none`. `substitute` is absent on
#: purpose -- see the module docstring.
ADVICE_TO_ENFORCEMENT = {
    ag_advice.ALLOW: "none",
    ag_advice.SKIP: "skip",
    ag_advice.LLM_SELF_REFLECT: "llm_self_reflect",
    ag_advice.USER_INSPECTION: "user_inspection",
    ag_advice.STOP: "stop",
}

#: How many times one step may be re-planned or rewritten before we give up and
#: stop. Without a bound, two policies that redirect to each other loop forever.
MAX_REDIRECTS = 3


@dataclass(frozen=True)
class Outcome:
    """What the agent loop should do next."""
    result: EnforceResult
    action: Action
    #: True when `action` is not the one that was judged, so the caller knows to
    #: guard it again rather than run it.
    redirected: bool = False
    note: str = ""


def _as_action(value, fallback: Action) -> Action:
    """Adapt whatever an enforcement class returned into an `Action`.

    Needed only because LLMSelfReflect returns a raw LangChain object (D-6).
    Everything else in enforcement.py already returns an Action.
    """
    if isinstance(value, Action):
        return value
    if value is None:
        return fallback
    try:
        return Action.from_langchain(value)
    except Exception:                                   # noqa: BLE001
        return fallback


def _known_tools(tools: Optional[Iterable[Any]]):
    if tools is None:
        return None
    return {getattr(tool, "name", str(tool)) for tool in tools}


def substitute(substitution: ag_advice.Substitution, action: Action,
               tools=None) -> Outcome:
    """Build the replacement call a `substitute` policy asked for.

    Fails closed twice, because a rewrite that goes wrong is a rewrite that
    silently does something other than the policy says:

      * an unknown tool becomes `stop`. LangChain would turn it into an
        `InvalidTool` observation the agent might simply ignore, which is a
        guard that did not guard.
      * unparseable `@substitute_args` becomes `stop` rather than being passed
        through as an opaque string.
    """
    from langchain_core.agents import AgentAction        # noqa: PLC0415

    known = _known_tools(tools)
    if known is not None and substitution.tool not in known:
        return _stop(f"substitution names an unknown tool {substitution.tool!r} "
                     f"(available: {', '.join(sorted(known)) or 'none'})")

    tool_input: Any = substitution.args
    if substitution.args:
        try:
            tool_input = json.loads(substitution.args)
        except ValueError:
            return _stop(f"@substitute_args for {substitution.tool!r} is not JSON: "
                         f"{substitution.args!r}")

    replacement = AgentAction(tool=substitution.tool, tool_input=tool_input,
                              log=f"substituted by policy: {substitution}")
    return Outcome(result=EnforceResult.CONTINUE,
                   action=Action.from_langchain(replacement),
                   redirected=True, note=f"substituted -> {substitution}")


def _stop(reason: str) -> Outcome:
    text = f"action stopped by cedar policy set ({reason})"
    return Outcome(result=EnforceResult.STOP,
                   action=Action.get_finish(text, text), note=reason)


def apply(verdict, action: Action, state, tools=None) -> Outcome:
    """One resolved verdict -> the next action, using AgentSpec's own classes."""
    outcome_advice = verdict.advice

    if outcome_advice == ag_advice.SUBSTITUTE:
        resolution = verdict.resolution
        if resolution is None or resolution.substitution is None:
            # advice.resolve only emits SUBSTITUTE with a substitution attached,
            # so this is unreachable by construction -- but the failure mode if
            # it ever were reachable is "silently do nothing", so guard it.
            return _stop("substitute advice arrived with nothing to substitute")
        return substitute(resolution.substitution, action, tools)

    key = ADVICE_TO_ENFORCEMENT.get(outcome_advice)
    if key is None:
        return _stop(f"no enforcement for advice {outcome_advice!r}")

    result, produced = ENFORCEMENT_TO_CLASS[key](state=state).apply(action)
    next_action = _as_action(produced, action)

    if result == EnforceResult.SELF_REFLECT:
        # The agent re-planned; the new action has not been guarded yet.
        return Outcome(result=result, action=next_action, redirected=True,
                       note="re-planned after llm_self_reflect")
    return Outcome(result=result, action=next_action)
