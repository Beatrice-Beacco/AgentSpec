"""The sensor registry (plan.md S2.1).

`agentguard/sensors.py` derives its metadata from the predicates themselves, so
these tests are not allowed to restate the module's own tables -- that would
assert nothing. They re-derive independently (from the AST, from the module each
predicate is defined in, by actually calling it) and compare.

Two of them are measurements rather than assertions about our code:
`test_embodied_sensors_raise_on_a_code_agent_trace` and
`test_no_registered_sensor_makes_a_model_call` record facts about the corpus
that S2.3 depends on. If either changes, the design decision resting on it needs
revisiting, which is why they are pinned here rather than left in a comment.
"""
import ast
import contextlib
import inspect
import io
import os
import sys
import textwrap
import warnings

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from agentguard import sensors                      # noqa: E402
from rules.manual.table import predicate_table      # noqa: E402


def source_names(predicate):
    """Every bare name in the predicate's body -- derived here, independently."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(textwrap.dedent(inspect.getsource(predicate)))
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def call(predicate, tool_input="print(6 * 7)", steps=()):
    with contextlib.redirect_stdout(io.StringIO()):
        return predicate("a task", tool_input, list(steps))


# ------------------------------------------------------------- S2.1 accept

def test_every_predicate_is_registered():
    """S2.1's acceptance test."""
    assert len(sensors.SENSORS) == 36
    assert set(sensors.SENSORS) == set(predicate_table)


def test_each_sensor_wraps_its_own_predicate():
    for name, sensor in sensors.SENSORS.items():
        assert sensor.name == name
        assert sensor.predicate is predicate_table[name]


def test_every_sensor_has_complete_metadata():
    for sensor in sensors.SENSORS.values():
        assert sensor.domain in sensors.DOMAINS, sensor.name
        assert sensor.cost in sensors.COSTS, sensor.name
        assert sensor.flags, sensor.name
        assert set(sensor.reads) <= set(sensors.PARAMETERS), sensor.name


# ------------------------------------------------------------------ domain

def test_domain_matches_the_module_the_predicate_came_from():
    for sensor in sensors.SENSORS.values():
        expected = sensors.MODULE_DOMAIN[sensor.predicate.__module__]
        assert sensor.domain == expected, sensor.name


def test_the_registered_corpus_is_two_domains_not_three():
    """The plan expects code/embodied/toolemu. Only two of them exist.

    `rules/manual/toolemu.py` is an empty file, and `rules/manual/terminal.py`
    keeps its four predicates in a private `table` dict that `table.py` never
    merges -- so neither domain reaches `predicate_table` at all. Pinned because
    S3.4 and S6.3 both assume a ToolEmu predicate layer that is not here.
    """
    counts = {d: len(sensors.by_domain(d)) for d in sensors.DOMAINS}
    assert counts == {"code": 25, "embodied": 11, "shell": 0, "toolemu": 0}


# -------------------------------------------------------------------- reads

def test_reads_is_derived_from_the_predicate_source():
    for sensor in sensors.SENSORS.values():
        names = source_names(sensor.predicate)
        expected = tuple(p for p in sensors.PARAMETERS if p in names)
        assert sensor.reads == expected, sensor.name


def test_only_one_predicate_reads_the_user_task():
    """35 of 36 judge the proposed action with no idea what was asked for.

    A guard that cannot relate the action to the request cannot tell "delete the
    temp file I asked you to delete" from "delete something else". The one
    exception is `predicate11`, whose name is itself a placeholder.
    """
    readers = [s.name for s in sensors.SENSORS.values() if "user_input" in s.reads]
    assert readers == ["predicate11"]


# --------------------------------------------------------------------- cost

def test_cost_follows_from_reads():
    for sensor in sensors.SENSORS.values():
        if sensor.cost == sensors.MODEL:
            continue
        expected = (sensors.HISTORY if "intermediate_steps" in sensor.reads
                    else sensors.INPUT)
        assert sensor.cost == expected, sensor.name


def test_the_cost_scale_is_ordered_cheapest_first():
    assert sensors.COSTS == (sensors.INPUT, sensors.HISTORY, sensors.MODEL)


def test_by_domain_returns_cheapest_first():
    for domain in sensors.DOMAINS:
        got = [sensors.COSTS.index(s.cost) for s in sensors.by_domain(domain)]
        assert got == sorted(got), domain


def test_no_registered_sensor_makes_a_model_call():
    """The MODEL cost class is real but currently empty.

    `terminal.py`'s `is_executing_malware` calls `llm_judge`, which invokes
    GPT-4 -- a network round trip and real money for every guarded action. It is
    not registered, so no sensor in the registry costs money today. When the
    shell domain is wired up this test flips, and the cost ordering starts to
    matter for more than tidiness.
    """
    assert sensors.by_cost(sensors.MODEL) == ()


# -------------------------------------------------------------------- flags

def test_each_sensor_sets_the_flag_named_after_it():
    for sensor in sensors.SENSORS.values():
        assert sensor.flags == (sensor.name,)


def test_flags_is_the_union_s22_generates_the_schema_from():
    assert sensors.FLAGS == tuple(sorted(sensors.SENSORS))
    assert len(sensors.FLAGS) == len(set(sensors.FLAGS)), "a flag is claimed twice"


# ------------------------------------------------------------------ lookups

def test_get_returns_the_sensor():
    assert sensors.get("destuctive_os_inst").name == "destuctive_os_inst"


def test_get_fails_loudly_and_says_how_many_exist():
    """AgentSpec's equivalent lookup fails mid-run instead (S0.12, is_malware)."""
    with pytest.raises(KeyError) as exc:
        sensors.get("is_malware")
    assert "36 are registered" in str(exc.value)


# ------------------------------------------- what the metadata is *for*

def test_a_code_sensor_agrees_with_its_predicate():
    sensor = sensors.get("destuctive_os_inst")
    assert sensors.evaluate(sensor, "t", 'os.remove("x")', []) is True
    assert sensors.evaluate(sensor, "t", "print(6 * 7)", []) is False


def test_every_code_sensor_is_total_on_ordinary_code_input():
    """The 25 code sensors survive a plain string with a plain step history."""
    for sensor in sensors.by_domain(sensors.CODE):
        call(sensor.predicate, steps=[("action", "observation")])


def test_embodied_sensors_raise_on_a_code_agent_trace():
    """Why `domain` is not decoration.

    Embodied predicates expect `intermediate_steps` shaped as their own
    observations; LangChain hands them (action, observation) tuples. The result
    is a TypeError, not a False -- so a domain-blind engine running every sensor
    would crash on every step rather than gather more evidence. That is the
    constraint S2.3's sensor selection has to respect.
    """
    raised = []
    for sensor in sensors.by_domain(sensors.EMBODIED):
        try:
            call(sensor.predicate, steps=[("action", "observation")])
        except Exception as exc:                       # noqa: BLE001
            raised.append((sensor.name, type(exc).__name__))

    assert sorted(n for n, _ in raised) == [
        "is_fragile",
        "is_holding_none_microwave_objects",
        "is_none_fridge_obj",
        "is_none_stoveburner_obj",
        "is_unsafe_fillliquid",
    ]


def test_the_way_a_wrong_domain_sensor_fails_is_not_even_stable():
    """Not one failure mode -- whatever the wrong data happens to hit.

    `is_unsafe_fillliquid` raises AttributeError on an input with spaces and
    IndexError on one without, because it splits the string and indexes the
    result. So "catch the known exception" is not a strategy available to
    S2.3: there is no known exception. Only not running the sensor works.
    """
    sensor = sensors.get("is_unsafe_fillliquid")
    seen = {}
    for label, tool_input in (("with spaces", "print(6 * 7)"),
                              ("without", "print(6*7)")):
        with pytest.raises(Exception) as exc:          # noqa: PT011
            call(sensor.predicate, tool_input=tool_input)
        seen[label] = type(exc.value).__name__

    assert seen == {"with spaces": "AttributeError", "without": "IndexError"}


def test_every_raising_sensor_is_one_the_metadata_warned_about():
    """The registry has to be able to predict the crashes, or it is useless.

    Every sensor that fails on a code trace is one whose `reads` include
    `intermediate_steps` -- cost HISTORY. Selecting on the metadata is therefore
    sufficient to avoid them; no separate blocklist is needed.
    """
    for sensor in sensors.SENSORS.values():
        try:
            call(sensor.predicate, steps=[("action", "observation")])
        except Exception:                              # noqa: BLE001
            assert sensor.cost == sensors.HISTORY, sensor.name


# --------------------------------------------------------- executor wiring

def test_the_executor_selects_through_the_registry():
    from agentguard import executor                   # noqa: PLC0415

    assert set(executor.ACTIVE_SENSORS) <= set(sensors.SENSORS)
    assert all(isinstance(s, sensors.Sensor) for s in executor.sensors().values())


def test_a_typo_in_the_active_set_fails_at_construction(monkeypatch):
    from agentguard import executor                   # noqa: PLC0415

    monkeypatch.setattr(executor, "ACTIVE_SENSORS", ("destuctive_os_instt",))
    with pytest.raises(KeyError):
        executor.sensors()
