"""Materialisation: RuleState -> (Request, Entities)  (plan.md S2.3).

S2.3's acceptance is a golden-file test: a fixed `RuleState` produces a fixed
JSON request. `tests/golden/request_python_repl.json` is that file, and it is
regenerated with

    .venv/bin/python -m tests.golden_request       (or: make golden)

A golden file is the right shape here because the request is the *interface*
between the two halves of the system. Anything that changes it -- a new sensor,
a schema variant, a different entity store -- changes what every policy sees,
and should be visible as a diff in review rather than discovered when a verdict
moves.
"""
import json
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from agentguard import request as ag_request       # noqa: E402
from agentguard import schema as ag_schema         # noqa: E402
from agentguard import sensors                     # noqa: E402
from agent import Action                           # noqa: E402
from state import RuleState                        # noqa: E402

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "golden", "request_python_repl.json")

#: The fixed RuleState. Deliberately the destructive scenario, so the golden
#: file records a request that actually reaches a Deny rather than an empty one.
FIXED_TOOL = "python_repl"
FIXED_INPUT = 'import os; os.remove("notes.txt")'
FIXED_TASK = "Delete the unimportant txt file"


def fixed_state(tool_input=FIXED_INPUT, tool_name=FIXED_TOOL, steps=()):
    from langchain_core.agents import AgentAction          # noqa: PLC0415
    action = Action.from_langchain(
        AgentAction(tool=tool_name, tool_input=tool_input, log="")
    )
    return RuleState(action=action, agent=None, intermediate_steps=list(steps),
                     user_input=FIXED_TASK)


def snapshot():
    """What the golden file holds. Sorted throughout, so diffs are readable."""
    material = ag_request.materialise(fixed_state())
    return {
        "domain": material.domain,
        "flags_variant": ag_schema.DEFAULT_VARIANT,
        "sensors_run": sorted(material.evaluated),
        "fired": material.fired,
        "errors": [str(e) for e in material.errors],
        "request": material.request,
        "entities": material.entities,
    }


# --------------------------------------------------------- S2.3 acceptance

def test_a_fixed_rulestate_produces_the_golden_request():
    """S2.3's acceptance test."""
    with open(GOLDEN, encoding="utf-8") as handle:
        expected = json.load(handle)
    assert snapshot() == expected, (
        "materialisation changed. If that is intended, regenerate with "
        "`make golden` and review the diff -- it is what every policy sees."
    )


def test_the_golden_request_is_stable_across_calls():
    assert snapshot() == snapshot()


def test_the_golden_request_is_the_one_the_engine_actually_sends():
    """The golden file is worthless if the engine builds something else."""
    from agentguard import executor                        # noqa: PLC0415

    verdict = executor.decide(executor.load_bundle(), fixed_state())
    assert verdict.materialisation.request == snapshot()["request"]


# ------------------------------------------------------------- selection

def test_the_whole_code_domain_runs():
    material = ag_request.materialise(fixed_state())
    assert sorted(material.evaluated) == sorted(
        s.name for s in sensors.by_domain(sensors.CODE))
    assert len(material.evaluated) == 25


def test_embodied_sensors_are_not_run_on_a_code_agent():
    """The reason selection is by domain at all (S2.1): they would raise."""
    material = ag_request.materialise(fixed_state())
    embodied = {s.name for s in sensors.by_domain(sensors.EMBODIED)}
    assert not (set(material.evaluated) & embodied)
    assert material.errors == ()


def test_an_explicit_selection_narrows_it():
    material = ag_request.materialise(fixed_state(), names=("destuctive_os_inst",))
    assert set(material.evaluated) == {"destuctive_os_inst"}


def test_selecting_the_embodied_domain_shows_why_domains_exist():
    """Ask for the wrong domain and materialisation reports failures instead of
    raising -- and, critically, does not report `false` for what it could not
    evaluate."""
    material = ag_request.materialise(
        fixed_state(steps=[("python_repl", "OK")]), domain=sensors.EMBODIED)

    assert material.errors, "expected the embodied sensors to fail on a code trace"
    failed = {failure.sensor for failure in material.errors}
    assert failed and not (failed & set(material.evaluated)), \
        "a sensor that raised must contribute no flag at all"


# --------------------------------------------------------- failing closed

def test_a_failing_sensor_leaves_its_flag_absent_not_false(monkeypatch):
    def explode(*_args, **_kwargs):
        raise RuntimeError("sensor exploded")

    monkeypatch.setattr(sensors, "evaluate", explode)
    material = ag_request.materialise(fixed_state(), names=("destuctive_os_inst",))

    assert material.evaluated == {}
    assert [f.sensor for f in material.errors] == ["destuctive_os_inst"]
    assert "sensor exploded" in str(material.errors[0])


def test_the_engine_stops_rather_than_deciding_on_missing_evidence(monkeypatch):
    """A missing flag reads to Cedar as "not evaluated", so a policy keyed on it
    cannot fire. Deciding anyway would be deciding on evidence we failed to
    gather."""
    from agentguard import executor                        # noqa: PLC0415

    def explode(*_args, **_kwargs):
        raise RuntimeError("sensor exploded")

    monkeypatch.setattr(sensors, "evaluate", explode)
    verdict = executor.decide(executor.load_bundle(), fixed_state())

    assert verdict.decision == "NotEvaluated"
    assert verdict.advice == "stop"
    assert verdict.errors


def test_a_finish_action_materialises_nothing_but_does_not_fail():
    finish = Action.get_finish("done", "done")
    state = RuleState(action=finish, agent=None, intermediate_steps=[])
    material = ag_request.materialise(state)

    assert material.evaluated == {} and material.errors == ()


# --------------------------------------------------------------- shaping

def test_the_uid_escapes_a_tool_name_from_model_output():
    material = ag_request.materialise(fixed_state(tool_name='python_repl", resource'))
    assert material.request["resource"] == \
        'AgentGuard::Tool::"python_repl\\", resource"'


def test_the_set_variant_loses_the_ran_and_said_no_evidence():
    material = ag_request.materialise(fixed_state(), variant=ag_schema.SET)
    flags = material.request["context"]["flags"]

    assert isinstance(flags, list)
    assert "destuctive_os_inst" in flags
    # 25 sensors ran; only the ones that fired survive into the request
    assert len(flags) < len(material.evaluated)


def test_an_unknown_variant_is_refused():
    with pytest.raises(ValueError, match="unknown flags variant"):
        ag_request.context_flags({"x": True}, "neither")
