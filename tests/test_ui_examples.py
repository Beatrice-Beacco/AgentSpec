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


@pytest.mark.legacy_only(
    "the bench's verdict is the legacy engine's; the Cedar panel is asserted "
    "separately below")
@pytest.mark.parametrize("example", EXAMPLES, ids=[e["name"][:2] for e in EXAMPLES])
def test_example_produces_its_stated_verdict(example):
    expected = EXPECTED[example["name"][:2]]
    assert run_example(example)["verdict"] == expected


@pytest.mark.legacy_only(
    "asserts the enforcement an AgentSpec rule names; needs S3.3 to compile it")
def test_user_inspection_flips_with_approval():
    """Example 5's whole point: the same input, two answers, two verdicts."""
    example = next(e for e in EXAMPLES if e["name"].startswith("5."))
    assert run_example(example, approve=True)["verdict"] == "ALLOWED"
    assert run_example(example, approve=False)["verdict"] == "SKIPPED"


@pytest.mark.legacy_only(
    "asserts order dependence, which Cedar removes by construction")
def test_order_dependence_is_real():
    """Example 8 claims swapping the rules flips the verdict. Verify both ways."""
    example = next(e for e in EXAMPLES if e["name"].startswith("8."))
    first, second = engine.split_rules(example["rule_text"])

    assert run_example({**example, "rule_text": first + second})["verdict"] == "SKIPPED"
    assert run_example({**example, "rule_text": second + first})["verdict"] == "STOPPED"


@pytest.mark.legacy_only(
    "the `why` panel explains AgentSpec rules, which the Cedar engine ignores")
def test_explain_reports_the_firing_rule():
    example = next(e for e in EXAMPLES if e["name"].startswith("1."))
    fired = [r["id"] for r in run_example(example)["explain"] if r["would_fire"]]
    assert fired == ["block_file_deletion"]


def test_broken_rule_is_reported_before_it_is_run():
    """The bench surfaces the parse errors the framework swallows at load time."""
    example = next(e for e in EXAMPLES if e["name"].startswith("7."))
    loaded = engine.load_rules(example["rule_text"])
    assert any(entry["errors"] for entry in loaded)


# ------------------------------------------------------------ Cedar panel
# plan.md S1.8. The panel decides the same call independently of the run, so
# these assert on the decision, not on a second agent invocation.

def example(prefix):
    return next(e for e in EXAMPLES if e["name"].startswith(prefix))


@pytest.fixture
def legacy_run(monkeypatch):
    """Pin the *run* to the legacy engine.

    These two tests compare the two engines, so the run has to be the legacy
    one whatever the ambient AGENTGUARD says -- otherwise `make test-cedar`
    turns them into a comparison of Cedar with itself, which always agrees.
    """
    monkeypatch.setenv("AGENTGUARD", "legacy")


def test_example_1_shows_a_real_cedar_verdict():
    """S1.8's acceptance test."""
    cedar = run_example(example("1."))["cedar"]
    assert cedar["status"] == "ok"
    assert cedar["decision"] == "Deny"
    assert cedar["advice"] == "stop"
    assert cedar["verdict"] == "STOPPED"
    assert "destuctive_os_inst" in cedar["flags"]
    assert [r["id"] for r in cedar["reasons"]] == ["no_destructive_os_call"]
    assert cedar["reasons"][0]["source"].startswith("agentspec:")


def test_example_2_shows_the_allow():
    """The false-positive half. A panel that only ever says Deny shows nothing."""
    cedar = run_example(example("2."))["cedar"]
    assert (cedar["decision"], cedar["advice"]) == ("Allow", "allow")
    assert "destuctive_os_inst" not in cedar["flags"]


def test_benign_arithmetic_still_trips_two_shipped_predicates():
    r"""S2.3 runs the whole code domain, and that immediately shows something.

    `print(6 * 7)` -- the bench's own example of a harmless action -- sets
    `write_to_io` (its pattern is `print\(.*?\)`, so every print is "I/O") and
    `is_buggy_ip_validation_code`, which is true of *every* input we can find,
    including the empty string. Neither is read by any policy in core.cedar, so
    the verdict is still Allow -- but they are what a compiled corpus rule would
    be keyed on, and they are the RQ2b false-positive floor.

    Pinned so that fixing either predicate, or narrowing the sensor selection,
    is a deliberate change rather than a silent one.
    """
    flags = run_example(example("2."))["cedar"]["flags"]
    assert "write_to_io" in flags
    assert "is_buggy_ip_validation_code" in flags


def test_the_panel_never_takes_the_run_down():
    """The bench exists to look at failures, so Cedar failures must be visible
    in the panel rather than fatal to the page."""
    for ex in EXAMPLES:
        assert run_example(ex)["cedar"]["status"] == "ok", ex["name"]


def test_example_3_is_where_the_engines_disagree(legacy_run):
    """"No rules loaded" does not mean "no policies".

    AgentSpec's rule list *is* its policy, so an empty list means nothing can
    fire. AgentGuard's policy set is ambient -- loaded from policies/ -- so the
    same input is still denied. A real semantic difference, surfaced by the
    panel rather than argued about; S2.7 has to decide what to do with it.
    """
    result = run_example(example("3."))
    assert result["verdict"] == "ALLOWED"
    assert result["cedar"]["decision"] == "Deny"


def test_example_7_decides_where_the_legacy_engine_crashes(legacy_run):
    """A rule that does not parse takes the AgentSpec run down mid-flight
    (S0.12). Cedar validates at load, so the same call still gets a decision."""
    result = run_example(example("7."))
    assert result["verdict"] == "ERROR"
    assert result["cedar"]["status"] == "ok"
    assert result["cedar"]["decision"] == "Deny"


def test_the_header_reports_which_engine_runs(monkeypatch):
    """With AGENTGUARD=cedar the "Why - per rule" panel describes rules that no
    longer decide anything, so the header must not keep saying "legacy"."""
    import app                                  # noqa: PLC0415

    client = app.app.test_client()
    monkeypatch.setenv("AGENTGUARD", "cedar")
    assert client.get("/api/state").get_json()["engine"] == "cedar"
    monkeypatch.setenv("AGENTGUARD", "legacy")
    assert client.get("/api/state").get_json()["engine"] == "legacy"


def test_rule_writes_are_confined_to_the_library():
    import app                                  # noqa: PLC0415
    with pytest.raises(ValueError):
        app._safe("../../../etc/passwd")
    with pytest.raises(ValueError):
        app._safe("src/rule.py")
    # _safe returns a native path, so the expected suffix has to be built with
    # os.path.join -- a literal "ui/rules/scratch.ar" only matches on POSIX.
    assert app._safe("ui/rules/scratch.ar").endswith(
        os.path.join("ui", "rules", "scratch.ar")
    )
