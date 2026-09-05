"""Shared fixtures for the AgentSpec test suite.

The repo has no package layout: modules under src/ import each other flatly
(`from rule import Rule`), so src/ has to be on sys.path before any test
module is imported. conftest.py is loaded first by pytest, so this is the
right place for it.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from langchain.tools import Tool                       # noqa: E402
from langchain_community.llms.fake import FakeListLLM  # noqa: E402

from controlled_agent_excector import initialize_controlled_agent  # noqa: E402
from rule import Rule                                              # noqa: E402


# The tool name the rules in these tests trigger on. `Rule.triggered` compares
# the event to the tool name verbatim, so the two must stay in sync.
TOOL_NAME = "python_repl"


@pytest.fixture
def tool_calls():
    """Every tool input the agent actually managed to execute, in order.

    An empty list is the assertion that enforcement stopped the action *before*
    the side effect, which is the whole point of the framework.
    """
    return []


@pytest.fixture
def recording_tool(tool_calls):
    """A stand-in for PythonREPL that records instead of executing.

    Deliberately not the real PythonREPL: these tests assert on whether the
    tool was reached, and running arbitrary generated code to find that out
    would make the suite non-hermetic (and, for the destructive cases,
    actually destructive).
    """
    def _run(command: str) -> str:
        tool_calls.append(command)
        return "OK"

    return Tool(
        name=TOOL_NAME,
        description="A Python shell. Input should be a valid python command.",
        func=_run,
    )


@pytest.fixture
def agent_factory(recording_tool):
    """Build a ControlledAgentExecutor driven by a scripted LLM.

    FakeListLLM replays `llm_script` in order and wraps around at the end, so
    the agent is deterministic and needs no API key. Each response must be in
    ReAct format for the zero-shot-react-description parser.
    """
    def _make(rule_texts, llm_script):
        rules = [Rule.from_text(t) for t in rule_texts]
        return initialize_controlled_agent(
            [recording_tool],
            FakeListLLM(responses=llm_script),
            agent="zero-shot-react-description",
            rules=rules,
            verbose=False,
        )

    return _make


# ------------------------------------------------------------------ scripts

def react_script(action_input, final_answer="done"):
    """A two-turn ReAct script: call the tool once, then finish."""
    return [
        f"Thought: I should use the tool.\n"
        f"Action: {TOOL_NAME}\n"
        f"Action Input: {action_input}",
        f"Thought: I have the answer.\nFinal Answer: {final_answer}",
    ]


DESTRUCTIVE_INPUT = 'import os; os.remove("notes.txt")'
BENIGN_INPUT = "print(6 * 7)"
