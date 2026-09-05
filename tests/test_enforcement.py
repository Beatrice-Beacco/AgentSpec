"""Enforcement-loop tests: does a rule actually stop the agent reaching the tool?

Two groups:

  * Scenarios A/B  -- end-to-end, with the real `destuctive_os_inst` predicate.
    A destructive action must be blocked; a benign one must get through. B is
    the false-positive guard: a rule that blocks everything would pass A alone.

  * Enforcement modes -- `check true` so the predicate is out of the picture
    and each test isolates one enforcement outcome (stop / skip / none).

Ported from smoke_test.py (S0.8).
"""
import pytest

from conftest import BENIGN_INPUT, DESTRUCTIVE_INPUT, TOOL_NAME, react_script, show
from rule import Rule


def rule_text(name, check, enforce):
    return (
        f"rule @{name}\n"
        f"trigger\n    {TOOL_NAME}\n"
        f"check\n    {check}\n"
        f"enforce\n    {enforce}\n"
        f"end\n"
    )


# `destuctive_os_inst` is spelled that way in AgentSpec.g4's PREDICATE token (sic).
# It matches os.remove / os.unlink, or pathlib+unlink together.
BLOCK_DELETION = rule_text("block_file_deletion", "destuctive_os_inst", "stop")


# --------------------------------------------------------------- scenario A/B

def test_destructive_action_is_blocked(agent_factory, tool_calls):
    """Scenario A: the agent proposes os.remove(...); the rule must stop it."""
    agent = agent_factory([BLOCK_DELETION], react_script(DESTRUCTIVE_INPUT))

    result = agent.invoke("Delete the unimportant txt file")
    show(result, tool_calls)

    assert tool_calls == [], "the tool ran despite the rule firing"
    assert "stopped by" in result["output"]
    assert result["intermediate_steps"] == []


def test_benign_action_is_allowed(agent_factory, tool_calls):
    """Scenario B: the same rule must not fire on arithmetic (no false positive)."""
    agent = agent_factory([BLOCK_DELETION], react_script(BENIGN_INPUT, "42"))

    result = agent.invoke("What is 6 times 7?")
    show(result, tool_calls)

    assert tool_calls == [BENIGN_INPUT]
    assert "stopped by" not in result["output"]
    assert result["output"] == "42"


def test_no_rules_means_no_interference(agent_factory, tool_calls):
    """Baseline: with an empty rule set the executor is a plain AgentExecutor."""
    agent = agent_factory([], react_script(DESTRUCTIVE_INPUT))

    result = agent.invoke("Delete the unimportant txt file")
    show(result, tool_calls)

    assert tool_calls == [DESTRUCTIVE_INPUT]
    assert result["output"] == "done"


# ---------------------------------------------------------- enforcement modes

def test_enforce_stop_ends_the_run(agent_factory, tool_calls):
    """`stop` -> the tool is skipped and the whole run terminates immediately."""
    agent = agent_factory(
        [rule_text("always_stop", "true", "stop")], react_script(BENIGN_INPUT)
    )

    result = agent.invoke("anything")
    show(result, tool_calls)

    assert tool_calls == []
    assert "stopped by" in result["output"]
    assert result["intermediate_steps"] == [], "stop must not leave a step behind"


def test_enforce_skip_drops_the_action_but_continues(agent_factory, tool_calls):
    """`skip` -> the tool is not reached, but the agent keeps planning.

    The skipped step is fed back as an observation, so the agent can react to
    having been blocked instead of just dying.
    """
    agent = agent_factory(
        [rule_text("always_skip", "true", "skip")], react_script(BENIGN_INPUT, "42")
    )

    result = agent.invoke("anything")
    show(result, tool_calls)

    assert tool_calls == []
    steps = result["intermediate_steps"]
    assert len(steps) == 1, "skip should record exactly one (action, observation)"
    _action, observation = steps[0]
    assert "skipped by user" in observation
    assert result["output"] == "42", "the run continued to a normal answer"


def test_enforce_none_lets_the_action_through(agent_factory, tool_calls):
    """`none` -> the rule fires but chooses not to intervene.

    Distinguishes "the rule matched" from "the rule blocked": the trigger and
    the predicate both hold here, and the tool still runs.
    """
    agent = agent_factory(
        [rule_text("always_none", "true", "none")], react_script(BENIGN_INPUT, "42")
    )

    result = agent.invoke("anything")
    show(result, tool_calls)

    assert tool_calls == [BENIGN_INPUT]
    assert result["output"] == "42"


def test_first_matching_rule_decides(agent_factory, tool_calls):
    """Rules are evaluated in list order and the first non-CONTINUE result wins.

    Documents current behaviour rather than endorsing it: this order dependence
    is one of the properties Cedar removes (`forbid` always wins, regardless of
    policy order). See plan.md S2.8.
    """
    permissive = rule_text("permissive", "true", "none")
    restrictive = rule_text("restrictive", "true", "stop")

    agent = agent_factory([permissive, restrictive], react_script(BENIGN_INPUT))
    result = agent.invoke("anything")
    show(result, tool_calls)

    assert tool_calls == []
    assert "stopped by" in result["output"]


# -------------------------------------------------------------- regressions

class TestTriggerMatching:
    """Regression tests for Rule.triggered (see the S0.4 fix).

    `Action.get_finish` sets input=None, and structured tools pass a dict.
    Both reach Rule.triggered because of and/or precedence in
    ControlledAgentExecutor.validate_and_enforce, so neither may crash.
    """

    RULE = Rule.from_text(BLOCK_DELETION)

    def test_none_input_does_not_crash(self):
        assert self.RULE.triggered("finish", None) is False

    def test_dict_input_does_not_crash(self):
        assert self.RULE.triggered("some_other_tool", {"task_id": "1"}) is False

    def test_matching_tool_name_triggers(self):
        assert self.RULE.triggered(TOOL_NAME, "anything") is True

    def test_any_event_triggers_on_everything(self):
        rule = Rule.from_text(rule_text("catch_all", "true", "none").replace(
            f"trigger\n    {TOOL_NAME}", "trigger\n    any"
        ))
        assert rule.triggered("literally_any_tool", None) is True
