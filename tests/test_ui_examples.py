"""The test bench's worked examples must actually do what they claim.

Every example in ui/examples.py carries an `expect` string shown on the help
page. If an example drifts from its description, the help page starts lying to
whoever is learning the tool -- so the expectation is asserted here.

Also covers the bench's own path guard: rule files may only be written inside
the rule library.
"""
import os
import sys

import pytest

UI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
if UI not in sys.path:
    sys.path.insert(0, UI)

import engine                                  # noqa: E402
from examples import EXAMPLES                  # noqa: E402


# Example name fragment -> the verdict it must produce.
EXPECTED = {
    "1.": "STOPPED",
    "2.": "ALLOWED",
    "3.": "ALLOWED",
    "4.": "SKIPPED",
    "5.": "ALLOWED",     # with approve on; the off case is asserted separately
    "6.": "STOPPED",
    "7.": "ERROR",       # a rule that does not parse takes the run down
    "8.": "SKIPPED",     # first matching rule wins
}


def run_example(example, approve=True):
    return engine.run(
        example["rule_text"], example["user_input"],
        example["tool_name"], example["tool_input"], approve=approve,
    )


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["name"][:2] for e in EXAMPLES])
def test_example_produces_its_stated_verdict(example):
    expected = EXPECTED[example["name"][:2]]
    assert run_example(example)["verdict"] == expected


def test_user_inspection_flips_with_approval():
    """Example 5's whole point: the same input, two answers, two verdicts."""
    example = next(e for e in EXAMPLES if e["name"].startswith("5."))
    assert run_example(example, approve=True)["verdict"] == "ALLOWED"
    assert run_example(example, approve=False)["verdict"] == "SKIPPED"


def test_order_dependence_is_real():
    """Example 8 claims swapping the rules flips the verdict. Verify both ways."""
    example = next(e for e in EXAMPLES if e["name"].startswith("8."))
    first, second = engine.split_rules(example["rule_text"])

    assert run_example({**example, "rule_text": first + second})["verdict"] == "SKIPPED"
    assert run_example({**example, "rule_text": second + first})["verdict"] == "STOPPED"


def test_explain_reports_the_firing_rule():
    example = next(e for e in EXAMPLES if e["name"].startswith("1."))
    fired = [r["id"] for r in run_example(example)["explain"] if r["would_fire"]]
    assert fired == ["block_file_deletion"]


def test_broken_rule_is_reported_before_it_is_run():
    """The bench surfaces the parse errors the framework swallows at load time."""
    example = next(e for e in EXAMPLES if e["name"].startswith("7."))
    loaded = engine.load_rules(example["rule_text"])
    assert any(entry["errors"] for entry in loaded)


def test_rule_writes_are_confined_to_the_library():
    import app                                  # noqa: PLC0415
    with pytest.raises(ValueError):
        app._safe("../../../etc/passwd")
    with pytest.raises(ValueError):
        app._safe("src/rule.py")
    assert app._safe("ui/rules/scratch.ar").endswith("ui/rules/scratch.ar")
