"""Shared fixtures for the AgentSpec test suite.

The repo has no package layout: modules under src/ import each other flatly
(`from rule import Rule`), so src/ has to be on sys.path before any test
module is imported. conftest.py is loaded first by pytest, so this is the
right place for it.
"""
import os
import re
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
# The repo root too, so `import agentguard` works: pytest puts tests/ on the
# path, not the directory above it.
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from langchain.tools import Tool                       # noqa: E402
from langchain_core.language_models.fake import FakeListLLM  # noqa: E402

from controlled_agent_excector import initialize_controlled_agent  # noqa: E402
from rule import Rule                                              # noqa: E402


# The tool name the rules in these tests trigger on. `Rule.triggered` compares
# the event to the tool name verbatim, so the two must stay in sync.
TOOL_NAME = "python_repl"

# AGENTSPEC_VERBOSE=1 makes the executor print its ReAct trace (thought,
# action, observation) so you can watch enforcement happen. Needs `pytest -s`
# to reach the terminal -- pytest captures stdout otherwise. See tests/README.md.
VERBOSE = os.environ.get("AGENTSPEC_VERBOSE") == "1"


# --------------------------------------------------------- engine selection

import agentguard                                              # noqa: E402

#: Tests whose *subject* is an AgentSpec rule: they pass one in and assert the
#: enforcement it names, or assert a property of the rule-list evaluation order.
#: They cannot run under the Cedar engine, which takes no rules -- until S3.3
#: compiles rules into policies there is nothing for it to decide on. Two of
#: them assert order dependence, which Cedar deliberately does not have, so they
#: will never be engine-agnostic.
#:
#: Marked rather than deleted: they are the record of the baseline's semantics,
#: and `make test-cedar` prints every skip with its reason.
LEGACY_ONLY = "legacy_only"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        f"{LEGACY_ONLY}(reason): the subject is an AgentSpec rule, so the test "
        "cannot run under AGENTGUARD=cedar")


def pytest_collection_modifyitems(config, items):
    """Skip legacy-only tests when the suite is forced onto the Cedar engine."""
    if not agentguard.enabled():
        return
    for item in items:
        marker = item.get_closest_marker(LEGACY_ONLY)
        if marker is None:
            continue
        reason = (marker.args[0] if marker.args
                  else "the subject is an AgentSpec rule")
        item.add_marker(pytest.mark.skip(
            reason=f"legacy engine only: {reason}"))


@pytest.fixture
def baseline_policy_dir(tmp_path, monkeypatch):
    """A valid policy set that guards nothing -- Cedar's "no rules loaded".

    The Cedar engine takes no `rules=` argument, so "run with an empty rule
    list" has no direct translation. The equivalent deployment is a policy set
    containing only the baseline permit, and this builds one. It also refuses to
    exist as an *empty* directory, because an engine with no policies at all
    allows everything (agentguard/engine.py).
    """
    (tmp_path / "schema.cedarschema").write_text(
        _generated_schema(), encoding="utf-8")
    (tmp_path / "baseline.cedar").write_text(
        '@id("baseline_allow_tools")\n'
        'permit (principal, action == AgentGuard::Action::"invoke", resource);\n',
        encoding="utf-8")
    monkeypatch.setenv(agentguard.POLICY_DIR_VAR, str(tmp_path))
    from agentguard import engine                              # noqa: PLC0415
    engine.load.cache_clear()
    yield str(tmp_path)
    engine.load.cache_clear()


def _generated_schema():
    from agentguard import schema                              # noqa: PLC0415
    return schema.generate()


@pytest.fixture(autouse=True)
def _verbose_header():
    """Label each test's block in the -s output, so runs aren't a wall of traces."""
    if VERBOSE:
        name = os.environ.get("PYTEST_CURRENT_TEST", "?").split("::")[-1].split(" ")[0]
        print(f"\n{'=' * 72}\n=== {name}\n{'=' * 72}")
    yield


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
        if VERBOSE:
            print(f"\n  >>> TOOL REACHED: {command!r}")
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
        if VERBOSE:
            print(f"  rules loaded      : {_describe(rules) or 'NONE - nothing can fire'}")
        return initialize_controlled_agent(
            [recording_tool],
            FakeListLLM(responses=llm_script),
            agent="zero-shot-react-description",
            rules=rules,
            verbose=VERBOSE,
        )

    return _make


def _describe(rules):
    """One-line summary per rule: @id, trigger, check, enforce."""
    out = []
    for r in rules:
        fields = {}
        for clause in ("trigger", "check", "enforce"):
            m = re.search(rf"^{clause}\s*\n\s*(.+)$", r.raw, re.M)
            fields[clause] = m.group(1).strip() if m else "?"
        out.append(f"@{r.id} [on {fields['trigger']} if {fields['check']} "
                   f"-> {fields['enforce']}]")
    return "; ".join(out)


def show(result, tool_calls):
    """Print the outcome of a run when AGENTSPEC_VERBOSE=1. No-op otherwise.

    Needed because the interesting part is not always in the chain trace. The
    `skip` path in ControlledAgentExecutor._iter_next_step yields an AgentStep
    directly without calling run_manager.on_agent_action, so verbose=True never
    prints it -- the only evidence a skip happened is in intermediate_steps.
    """
    if not VERBOSE:
        return
    print("\n  --- outcome ---")
    print(f"  tool calls        : {tool_calls or 'NONE (blocked before the tool)'}")
    print(f"  final output      : {result['output'][:70]!r}")
    steps = result.get("intermediate_steps", [])
    print(f"  intermediate steps: {len(steps)}")
    for i, (action, observation) in enumerate(steps, 1):
        print(f"    [{i}] action     : {action.tool}({action.tool_input!r})")
        print(f"        observation: {str(observation).strip()[:100]!r}")
    print()


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
