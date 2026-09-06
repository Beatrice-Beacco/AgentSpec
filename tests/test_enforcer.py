"""Advice -> enforcement (plan.md S2.6).

S2.6's acceptance is one test per enforcement mode. There are six: the five on
the lattice plus `substitute`, and two of the six needed more than routing --
both because the baseline's implementation is broken rather than because we
disagreed with it (docs/findings.md D-5, D-6).

The unit tests drive `enforcer.apply` directly. The end-to-end ones go through
a real `CedarControlledAgentExecutor`, because "the outcome was produced" and
"the agent did the right thing" are different claims and only the second one
matters.
"""
import builtins
import os
import sys

import pytest

cedarpy = pytest.importorskip("cedarpy")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from conftest import BENIGN_INPUT, TOOL_NAME, react_script    # noqa: E402

from agentguard import advice as ag_advice        # noqa: E402
from agentguard import enforcer                   # noqa: E402
from agentguard import engine                     # noqa: E402
from agent import Action                          # noqa: E402
from enforcement import EnforceResult             # noqa: E402
from state import RuleState                       # noqa: E402


def an_action(tool=TOOL_NAME, tool_input=BENIGN_INPUT):
    from langchain_core.agents import AgentAction          # noqa: PLC0415
    return Action.from_langchain(
        AgentAction(tool=tool, tool_input=tool_input, log=""))


def a_state(action, user_input=None):
    return RuleState(action=action, agent=None, intermediate_steps=[],
                     user_input=user_input if user_input is not None
                     else {"input": "do a thing"})


def a_verdict(advice_value, substitution=None):
    resolution = ag_advice.Resolution(
        advice=advice_value,
        contributing=(ag_advice.Contribution("p", advice_value, substitution),),
        substitution=substitution)
    return engine.Verdict(id="p", raw="policy @p", advice=advice_value,
                          decision="Deny", resolution=resolution)


class StubTool:
    def __init__(self, name):
        self.name = name


# --------------------------------------------- one test per enforcement mode

def test_allow_lets_the_action_through():
    action = an_action()
    outcome = enforcer.apply(a_verdict(ag_advice.ALLOW), action, a_state(action))

    assert outcome.result == EnforceResult.CONTINUE
    assert outcome.action is action
    assert not outcome.redirected


def test_skip_suppresses_the_action():
    action = an_action()
    outcome = enforcer.apply(a_verdict(ag_advice.SKIP), action, a_state(action))

    assert outcome.result == EnforceResult.SKIP


def test_stop_ends_the_run():
    action = an_action()
    outcome = enforcer.apply(a_verdict(ag_advice.STOP), action, a_state(action))

    assert outcome.result == EnforceResult.STOP


@pytest.mark.parametrize("answer,expected", [
    ("yes", EnforceResult.CONTINUE),
    ("no", EnforceResult.SKIP),
])
def test_user_inspection_follows_the_user(answer, expected, monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: answer)
    action = an_action()
    outcome = enforcer.apply(a_verdict(ag_advice.USER_INSPECTION), action,
                             a_state(action))

    assert outcome.result == expected


def test_llm_self_reflect_replans_and_the_result_is_usable(monkeypatch):
    """The adapter that exists because of D-6.

    LLMSelfReflect hands back the raw LangChain object agent.plan() returned.
    The legacy executor feeds that straight into its own loop and dies on
    `action.is_finish()`. We wrap it, so the outcome is an Action either way.
    """
    from langchain_core.agents import AgentAction          # noqa: PLC0415

    class Replanner:
        def plan(self, steps, callbacks=None, **_kw):
            return AgentAction(tool=TOOL_NAME, tool_input="print(2)", log="replanned")

    action = an_action()
    state = a_state(action)
    object.__setattr__(state, "agent", Replanner())

    outcome = enforcer.apply(a_verdict(ag_advice.LLM_SELF_REFLECT), action, state)

    assert outcome.result == EnforceResult.SELF_REFLECT
    assert isinstance(outcome.action, Action), "the D-6 adapter did not run"
    assert outcome.action.is_finish() is False
    assert outcome.action.input == "print(2)"
    assert outcome.redirected, "a re-planned action has not been guarded yet"


def test_substitute_rewrites_the_call():
    """The one outcome with nothing to reuse -- InvokeAction is a no-op (D-5)."""
    action = an_action()
    substitution = ag_advice.Substitution(tool="safe_tool", args='{"cmd": "ls"}')
    outcome = enforcer.apply(a_verdict(ag_advice.SUBSTITUTE, substitution), action,
                             a_state(action), tools=[StubTool("safe_tool")])

    assert outcome.result == EnforceResult.CONTINUE
    assert outcome.redirected
    assert outcome.action.name == "safe_tool"
    assert outcome.action.input == {"cmd": "ls"}


# ------------------------------------------------- substitution fails closed

def test_substituting_to_an_unknown_tool_stops():
    """LangChain would turn it into an InvalidTool observation the agent might
    ignore -- a guard that did not guard."""
    action = an_action()
    substitution = ag_advice.Substitution(tool="nonexistent", args="")
    outcome = enforcer.apply(a_verdict(ag_advice.SUBSTITUTE, substitution), action,
                             a_state(action), tools=[StubTool("safe_tool")])

    assert outcome.result == EnforceResult.STOP
    assert "unknown tool" in outcome.note


def test_unparseable_substitute_args_stops():
    action = an_action()
    substitution = ag_advice.Substitution(tool="safe_tool", args="{not json")
    outcome = enforcer.apply(a_verdict(ag_advice.SUBSTITUTE, substitution), action,
                             a_state(action), tools=[StubTool("safe_tool")])

    assert outcome.result == EnforceResult.STOP
    assert "not JSON" in outcome.note


def test_substitute_advice_with_no_substitution_stops():
    """Unreachable via advice.resolve, but the failure mode would be silence."""
    action = an_action()
    outcome = enforcer.apply(a_verdict(ag_advice.SUBSTITUTE), action, a_state(action))

    assert outcome.result == EnforceResult.STOP


def test_a_substitution_carries_its_provenance():
    action = an_action()
    substitution = ag_advice.Substitution(tool="safe_tool", args='{"cmd": "ls"}')
    outcome = enforcer.apply(a_verdict(ag_advice.SUBSTITUTE, substitution), action,
                             a_state(action), tools=[StubTool("safe_tool")])

    assert "substituted by policy" in outcome.action.unwrap().log


# ------------------------------------------------------- reuse, not rewrite

def test_every_lattice_outcome_is_applied_by_agentspecs_own_class():
    """The instruction for this step was "reuse them; don't rewrite"."""
    from enforcement import ENFORCEMENT_TO_CLASS            # noqa: PLC0415

    assert set(enforcer.ADVICE_TO_ENFORCEMENT) == set(ag_advice.LATTICE)
    for key in enforcer.ADVICE_TO_ENFORCEMENT.values():
        assert key in ENFORCEMENT_TO_CLASS


def test_substitute_is_the_only_outcome_we_implement_ourselves():
    assert ag_advice.SUBSTITUTE not in enforcer.ADVICE_TO_ENFORCEMENT


# --------------------------------------------------------------- end to end


@pytest.fixture
def cedar_env(monkeypatch):
    monkeypatch.setenv("AGENTGUARD", "cedar")


def test_a_stopping_policy_stops_a_real_run(cedar_env, agent_factory, tool_calls):
    from conftest import DESTRUCTIVE_INPUT                  # noqa: PLC0415

    agent = agent_factory([], react_script(DESTRUCTIVE_INPUT))
    result = agent.invoke("Delete the unimportant txt file")

    assert tool_calls == []
    assert "stopped by" in result["output"]


def test_a_redirect_is_guarded_again_and_bounded(cedar_env, agent_factory,
                                                 tool_calls, monkeypatch):
    """A rewrite replaces a call the policy set has just judged, so it goes back
    through the policy set rather than straight to the tool -- otherwise
    @substitute_tool would be a way around the guard. Bounded, because two
    policies that redirect to each other would loop forever.
    """
    guarded = []

    def always_redirect(verdict, action, state, tools=None):
        guarded.append(action.name)
        return enforcer.Outcome(result=EnforceResult.CONTINUE, action=an_action(),
                                redirected=True, note="redirected again")

    monkeypatch.setattr("agentguard.executor.decide",
                        lambda bundle, state, domain=None: a_verdict(ag_advice.STOP))
    monkeypatch.setattr(enforcer, "apply", always_redirect)

    agent = agent_factory([], react_script(BENIGN_INPUT, "42"))
    result = agent.invoke("anything")

    assert tool_calls == [], "an unbounded redirect reached the tool"
    assert "gave up after" in result["output"]
    # the original action plus MAX_REDIRECTS re-guards, then it gives up
    assert len(guarded) == enforcer.MAX_REDIRECTS + 1


def test_a_substitution_runs_the_replacement_tool(cedar_env, agent_factory,
                                                  tool_calls, monkeypatch):
    """End to end: the policy asks for a rewrite and the *other* tool is what runs."""
    substitution = ag_advice.Substitution(tool=TOOL_NAME, args='"print(99)"')
    calls = {"n": 0}

    def decide_once(bundle, state, domain=None):
        """Substitute the first action; allow the re-guarded replacement through."""
        calls["n"] += 1
        if calls["n"] == 1:
            return a_verdict(ag_advice.SUBSTITUTE, substitution)
        return engine.Verdict(id="__allow__", raw="", advice=ag_advice.ALLOW,
                              decision="Allow")

    monkeypatch.setattr("agentguard.executor.decide", decide_once)

    agent = agent_factory([], react_script(BENIGN_INPUT, "42"))
    agent.invoke("anything")

    assert tool_calls == ["print(99)"], "the replacement call did not run"
    assert calls["n"] == 2, "the replacement was not guarded again"
