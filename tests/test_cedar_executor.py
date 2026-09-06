"""The walking skeleton, end to end: Cedar decides (plan.md S1.7).

S1.7's acceptance test is verdict *parity*. The old `smoke_test.py` is gone
(S0.8 turned it into tests/), so its two scenarios live in
tests/test_enforcement.py and are what gets compared here:

    A  the agent proposes os.remove(...)  ->  blocked, tool never reached
    B  the agent proposes print(6 * 7)    ->  allowed, tool runs

Both engines are built from the same agent, the same tools and the same
scripted LLM, and every test below asserts they agree. Parity on the *whole*
suite is S2.7; at this point the Cedar engine knows one sensor and two
policies, so it can only be expected to match on the scenarios those cover.
"""
import os
import sys

import pytest

from conftest import BENIGN_INPUT, DESTRUCTIVE_INPUT, TOOL_NAME, react_script

cedarpy = pytest.importorskip("cedarpy")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import agentguard                                        # noqa: E402
from agentguard import executor as ag                    # noqa: E402
from agent import Action                                 # noqa: E402
from state import RuleState                              # noqa: E402


@pytest.fixture
def cedar_env(monkeypatch):
    monkeypatch.setenv("AGENTGUARD", "cedar")


@pytest.fixture
def bundle():
    return ag.load_bundle()


def state_for(tool_input, tool_name=TOOL_NAME, user_input="anything"):
    """A RuleState the way ControlledAgentExecutor._iter_next_step builds one."""
    from langchain_core.agents import AgentAction              # noqa: PLC0415
    action = Action.from_langchain(
        AgentAction(tool=tool_name, tool_input=tool_input, log="")
    )
    return action, RuleState(action=action, agent=None, intermediate_steps=[],
                             user_input=user_input)


# ------------------------------------------------------------ the switch

def test_legacy_is_the_default(monkeypatch):
    monkeypatch.delenv("AGENTGUARD", raising=False)
    assert not agentguard.enabled()


@pytest.mark.parametrize("value,expected", [
    ("cedar", True), ("CEDAR", True), (" cedar ", True),
    ("legacy", False), ("", False), ("cedarish", False),
])
def test_the_env_flag_is_read_exactly(value, expected, monkeypatch):
    monkeypatch.setenv("AGENTGUARD", value)
    assert agentguard.enabled() is expected


def test_the_factory_builds_the_cedar_executor(cedar_env, agent_factory):
    agent = agent_factory([], react_script(BENIGN_INPUT))
    assert isinstance(agent, ag.CedarControlledAgentExecutor)


def test_the_factory_builds_the_legacy_executor_by_default(monkeypatch, agent_factory):
    # Explicitly unset rather than trusting the ambient value: `make test-cedar`
    # runs this whole suite with AGENTGUARD=cedar, and a test whose meaning
    # changes with the environment is not testing the default.
    monkeypatch.delenv("AGENTGUARD", raising=False)
    agent = agent_factory([], react_script(BENIGN_INPUT))
    assert not isinstance(agent, ag.CedarControlledAgentExecutor)


# ----------------------------------------------------- S1.7 acceptance

def test_scenario_a_destructive_action_is_blocked(cedar_env, agent_factory, tool_calls):
    """Scenario A through Cedar: same verdict as tests/test_enforcement.py."""
    agent = agent_factory([], react_script(DESTRUCTIVE_INPUT))
    result = agent.invoke("Delete the unimportant txt file")

    assert tool_calls == [], "the tool ran despite the policy denying"
    assert "stopped by" in result["output"]
    assert result["intermediate_steps"] == []


def test_scenario_b_benign_action_is_allowed(cedar_env, agent_factory, tool_calls):
    """Scenario B: the false-positive guard. A engine that denies all passes A."""
    agent = agent_factory([], react_script(BENIGN_INPUT, "42"))
    result = agent.invoke("What is 6 times 7?")

    assert tool_calls == [BENIGN_INPUT]
    assert result["output"] == "42"


@pytest.mark.parametrize("tool_input,final,expect_tool", [
    (DESTRUCTIVE_INPUT, "done", False),
    (BENIGN_INPUT, "42", True),
])
def test_both_engines_reach_the_same_verdict(tool_input, final, expect_tool,
                                             monkeypatch, agent_factory, tool_calls):
    """The parity claim itself, run rather than asserted twice by hand.

    The legacy engine needs its rule to be loaded; the Cedar engine reads the
    equivalent policy from policies/core.cedar. Same scenario, same agent, two
    decision procedures.
    """
    from test_enforcement import BLOCK_DELETION                # noqa: PLC0415

    verdicts = {}
    for engine, rules in (("legacy", [BLOCK_DELETION]), ("cedar", [])):
        monkeypatch.setenv("AGENTGUARD", engine)
        tool_calls.clear()
        agent = agent_factory(rules, react_script(tool_input, final))
        result = agent.invoke("anything")
        verdicts[engine] = (list(tool_calls), "stopped by" in result["output"])

    assert verdicts["cedar"] == verdicts["legacy"], verdicts
    assert bool(verdicts["cedar"][0]) is expect_tool


# ------------------------------------------------------------- sensors

def test_the_sensor_fires_on_a_destructive_call():
    _action, state = state_for(DESTRUCTIVE_INPUT)
    assert ag.run_sensors(state) == {"destuctive_os_inst": True}


def test_the_sensor_stays_quiet_on_arithmetic():
    """Present and false -- the sensor ran and said no.

    Not the same as absent, which means nobody looked. Under the record schema
    (S2.2) Cedar makes a policy distinguish the two, so the request has to.
    """
    _action, state = state_for(BENIGN_INPUT)
    assert ag.run_sensors(state) == {"destuctive_os_inst": False}
    assert ag.fired(ag.run_sensors(state)) == []


def test_a_finish_action_has_nothing_to_sense():
    """AgentFinish carries input=None; the predicates all index into a string.

    This is the S0.4 crash in a new place -- worth pinning here rather than
    rediscovering it the first time an agent completes normally.
    """
    finish = Action.get_finish("done", "done")
    state = RuleState(action=finish, agent=None, intermediate_steps=[])
    assert ag.run_sensors(state) == {}


def test_a_dict_tool_input_does_not_crash_the_sensors():
    """Structured tools pass a dict, not a string."""
    _action, state = state_for({"task_id": "1"})
    assert ag.run_sensors(state) == {"destuctive_os_inst": False}


# ------------------------------------------------------------ decisions

def test_decide_denies_with_stop(bundle):
    _action, state = state_for(DESTRUCTIVE_INPUT)
    verdict = ag.decide(bundle, state)
    assert verdict.decision == "Deny"
    assert verdict.advice == "stop"
    assert verdict.id == "no_destructive_os_call"
    assert "agentspec:" in verdict.raw


def test_decide_allows_a_benign_call(bundle):
    _action, state = state_for(BENIGN_INPUT)
    verdict = ag.decide(bundle, state)
    assert verdict.decision == "Allow"
    assert verdict.advice == "allow"


def test_the_forbid_is_scoped_to_its_tool(bundle):
    """The same dangerous input through a different tool is not this policy's business."""
    _action, state = state_for(DESTRUCTIVE_INPUT, tool_name="shell")
    assert ag.decide(bundle, state).decision == "Allow"


def test_a_tool_name_cannot_break_out_of_its_uid(bundle):
    """The tool name comes from model output, so it is attacker-influenced.

    Unescaped, `python_repl"` would close the entity uid early. The decision
    must stay well-formed -- and must not accidentally match the policy that
    names the real python_repl.
    """
    _action, state = state_for(DESTRUCTIVE_INPUT, tool_name='python_repl", resource')
    verdict = ag.decide(bundle, state)
    assert verdict.errors == ()
    assert verdict.decision == "Allow"


# --------------------------------------------------------- failing closed

def test_an_engine_error_is_not_an_allow(bundle, monkeypatch):
    """Cedar answers NoDecision -- not an exception -- when it cannot evaluate.

    A malformed entity store does exactly this. If "not Deny" were read as
    permission, an engine fault would become a silent allow: the failure mode
    the whole project exists to remove. Found while writing S1.7.
    """
    monkeypatch.setattr(ag, "build_entities", lambda tool: [
        {"uid": {"type": "AgentGuard::Agent", "id": "agent"},
         "attrs": {"framework": 42}, "parents": []},
    ])
    _action, state = state_for(BENIGN_INPUT)
    verdict = ag.decide(bundle, state)

    assert verdict.decision != "Allow"
    assert verdict.advice == "stop"
    assert verdict.errors


def test_an_unvalidatable_policy_set_refuses_to_load(tmp_path):
    """A policy that does not type-check must stop the agent starting.

    AgentSpec accepts a malformed rule at load and raises mid-run instead
    (tests/test_fail_open.py). This is the same situation, decided the other
    way. S2.5 widens it to the whole engine and flips those xfails.
    """
    (tmp_path / "schema.cedarschema").write_text(
        open(os.path.join(agentguard.POLICY_DIR, "schema.cedarschema"),
             encoding="utf-8").read(), encoding="utf-8")
    (tmp_path / "broken.cedar").write_text(
        '@id("x") permit (principal, action == AgentGuard::Action::"invoke", resource) '
        'when { context.flgs.contains("y") };', encoding="utf-8")

    with pytest.raises(ag.PolicyError) as exc:
        ag.load_bundle(str(tmp_path))
    assert "flgs" in str(exc.value)


def test_an_empty_policy_directory_refuses_to_load(tmp_path):
    with pytest.raises(ag.PolicyError):
        ag.load_bundle(str(tmp_path))


# ---------------------------------------------------------- the lattice

@pytest.mark.parametrize("advice,expected", [
    (["stop"], "stop"),
    (["skip", "stop"], "stop"),
    (["stop", "skip"], "stop"),
    (["allow", "skip"], "skip"),
    (["user_inspection", "llm_self_reflect"], "user_inspection"),
])
def test_the_join_takes_the_most_restrictive(advice, expected):
    assert ag.join(advice) == expected


def test_every_advice_maps_onto_an_enforcement_class():
    """The lattice is useless if an outcome has nothing to apply it with."""
    from enforcement import ENFORCEMENT_TO_CLASS                # noqa: PLC0415
    assert set(ag.ADVICE_TO_ENFORCEMENT) == set(ag.ADVICE_LATTICE)
    assert all(key in ENFORCEMENT_TO_CLASS
               for key in ag.ADVICE_TO_ENFORCEMENT.values())


# -------------------------------------------------------- parse once only

def test_the_policy_set_is_parsed_once(monkeypatch):
    """S1.4's finding, enforced: re-parsing per decision costs 2x and is the
    mistake AgentSpec makes on every action (S0.11, 77.6% of guard time)."""
    ag.load_bundle.cache_clear()
    calls = []
    real = ag.PolicySet.from_str
    monkeypatch.setattr(ag.PolicySet, "from_str",
                        staticmethod(lambda text: calls.append(1) or real(text)))
    try:
        for _ in range(3):
            bundle = ag.load_bundle()
            _action, state = state_for(DESTRUCTIVE_INPUT)
            ag.decide(bundle, state)
    finally:
        ag.load_bundle.cache_clear()
    assert len(calls) == 1
