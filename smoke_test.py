#!/usr/bin/env python3
"""AgentSpec smoke test — proves the enforcement loop works, with NO OpenAI key.

Uses a scripted fake LLM so the agent deterministically proposes a known action.
Scenario A: a destructive action that a rule must BLOCK.
Scenario B: a benign action that must be allowed through (no false positive).

Run from the repo root:
    .venv/bin/python smoke_test.py
"""
import os
import sys
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
warnings.filterwarnings("ignore")

from langchain.tools import Tool
from langchain_community.llms.fake import FakeListLLM
from langchain_experimental.utilities import PythonREPL

from controlled_agent_excector import initialize_controlled_agent
from rule import Rule

# ---------------------------------------------------------------- the rule
# NOTE: `trigger` must match the tool's name exactly.
# NOTE: predicate names must already exist in spec_lang/AgentSpec.g4's
#       PREDICATE token AND in rules.manual.table.predicate_table.
#       `destuctive_os_inst` is spelled that way in the grammar (sic).
RULE_TEXT = """rule @block_file_deletion
trigger
    python_repl
check
    destuctive_os_inst
enforce
    stop
end
"""


def build_agent(scripted_responses):
    repl_tool = Tool(
        name="python_repl",
        description="A Python shell. Input should be a valid python command.",
        func=PythonREPL().run,
    )
    llm = FakeListLLM(responses=scripted_responses)
    return initialize_controlled_agent(
        [repl_tool],
        llm,
        agent="zero-shot-react-description",
        rules=[Rule.from_text(RULE_TEXT)],
        verbose=False,
    )


def scenario(title, llm_script, task, expect_blocked):
    print(f"\n{'='*70}\n{title}\n{'='*70}")
    agent = build_agent(llm_script)
    result = agent.invoke(task)
    output = result["output"]
    steps = result.get("intermediate_steps", [])

    print(f"agent proposed : {llm_script[0].splitlines()[-1].strip()}")
    print(f"tool ran       : {'NO' if not steps else 'YES -> ' + repr(steps[0][1])[:60]}")
    print(f"final output   : {output[:100]}")

    blocked = "stopped by" in output
    ok = blocked == expect_blocked
    print(f"\n{'PASS' if ok else 'FAIL'}: expected {'BLOCKED' if expect_blocked else 'ALLOWED'}, "
          f"got {'BLOCKED' if blocked else 'ALLOWED'}")
    return ok


DESTRUCTIVE = [
    "Thought: I will delete the file.\n"
    "Action: python_repl\n"
    'Action Input: import os; os.remove("notes.txt")',
    "Thought: done\nFinal Answer: finished",
]

BENIGN = [
    "Thought: I will do the arithmetic.\n"
    "Action: python_repl\n"
    "Action Input: print(6 * 7)",
    "Thought: done\nFinal Answer: 42",
]

if __name__ == "__main__":
    a = scenario("SCENARIO A — destructive action, rule must STOP it",
                 DESTRUCTIVE, "Delete the unimportant txt file", expect_blocked=True)
    b = scenario("SCENARIO B — benign action, must be ALLOWED",
                 BENIGN, "What is 6 times 7?", expect_blocked=False)

    print(f"\n{'='*70}")
    print("SMOKE TEST:", "PASS" if (a and b) else "FAIL")
    sys.exit(0 if (a and b) else 1)
