"""Generating the schema from the sensor registry (plan.md S2.2).

S2.2's acceptance is "regenerating the schema after adding a sensor requires no
hand-editing", which is two claims:

  * the file on disk is exactly what the generator produces from the current
    registry -- so it cannot be hand-edited or go stale unnoticed;
  * adding a sensor and regenerating is sufficient -- there is no second place
    to update.

Both are tested by doing it, not by inspecting the generator's source.

The rest measures the two variants against each other, which is the question
thesis C.2 poses: `Set<String>` versus a record of Bools, and within the record,
required versus optional attributes. Those measurements are the justification
for the shape of the generated file, so they live next to it.
"""
import os
import sys

import pytest

cedarpy = pytest.importorskip("cedarpy")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from agentguard import schema as ag_schema        # noqa: E402
from agentguard import sensors                    # noqa: E402

INVOKE = 'AgentGuard::Action::"invoke"'
ENTITIES = [
    {"uid": {"type": "AgentGuard::Agent", "id": "a"},
     "attrs": {"framework": "langchain"}, "parents": []},
    {"uid": {"type": "AgentGuard::Tool", "id": "python_repl"},
     "attrs": {"kind": "code_exec", "reversible": False}, "parents": []},
]


def compiled(variant=ag_schema.RECORD, flags=None):
    return cedarpy.Schema.from_str(ag_schema.generate(variant, flags))


def decide(policy, flags, schema):
    return cedarpy.is_authorized({
        "principal": 'AgentGuard::Agent::"a"',
        "action": INVOKE,
        "resource": 'AgentGuard::Tool::"python_repl"',
        "context": {"flags": flags},
    }, policy, ENTITIES, schema)


# --------------------------------------------------------- S2.2 acceptance

def test_the_file_on_disk_is_what_the_generator_produces():
    """No hand-editing: the artifact and the registry cannot drift apart."""
    ok, reason = ag_schema.is_current()
    assert ok, reason


def test_adding_a_sensor_needs_no_edit_to_the_generator():
    """The acceptance criterion, performed rather than asserted.

    A new flag appears in the output with no change to any template, and the
    only input is the registry.
    """
    before = ag_schema.generate(flags=sensors.FLAGS)
    after = ag_schema.generate(flags=tuple(sensors.FLAGS) + ("reads_private_key",))

    assert "reads_private_key?: Bool" in after
    assert "reads_private_key" not in before
    # and it is still a schema, not just text with a line added
    cedarpy.Schema.from_str(after)


def test_a_new_flag_is_immediately_usable_in_a_policy():
    schema = compiled(flags=tuple(sensors.FLAGS) + ("reads_private_key",))
    policy = (f'permit (principal, action == {INVOKE}, resource) when '
              '{ context.flags has reads_private_key && context.flags.reads_private_key };')
    assert cedarpy.validate_policies(policy, schema).validation_passed


def test_generation_is_deterministic():
    """`make validate` compares bytes, so a timestamp in the header would make
    the staleness check meaningless."""
    assert ag_schema.generate() == ag_schema.generate()


def test_every_registered_sensor_has_a_flag_in_the_schema():
    text = ag_schema.generate()
    for flag in sensors.FLAGS:
        assert f"{flag}?: Bool" in text, flag


# -------------------------------------------------------------- variants

def test_both_variants_are_generatable_and_valid():
    for variant in ag_schema.VARIANTS:
        cedarpy.Schema.from_str(ag_schema.generate(variant))


def test_the_variant_is_readable_back_off_the_file():
    """The request builder reads the shape from the schema rather than being
    told separately, so the two cannot disagree."""
    for variant in ag_schema.VARIANTS:
        assert ag_schema.variant_of(ag_schema.generate(variant)) == variant


def test_a_schema_without_a_marker_is_rejected():
    with pytest.raises(ValueError, match="regenerate"):
        ag_schema.variant_of("entity Agent = { framework: String };")


def test_the_default_is_the_record_variant():
    assert ag_schema.DEFAULT_VARIANT == ag_schema.RECORD


def test_the_record_catches_a_typo_the_set_variant_misses():
    """Thesis C.2's question, answered by running it both ways.

    The same misspelled flag: unchecked under `Set<String>` (so the policy
    silently never fires) and rejected by name under the record.
    """
    set_policy = (f'permit (principal, action == {INVOKE}, resource) '
                  'when { context.flags.contains("destuctive_os_inzt") };')
    record_policy = (f'permit (principal, action == {INVOKE}, resource) '
                     'when { context.flags.destuctive_os_inzt };')

    assert cedarpy.validate_policies(
        set_policy, compiled(ag_schema.SET)).validation_passed
    assert not cedarpy.validate_policies(
        record_policy, compiled(ag_schema.RECORD)).validation_passed


# ----------------------------------------- why the Bools are *optional*

GUARDED = (f'permit (principal, action == {INVOKE}, resource) when '
           '{ context.flags has destuctive_os_inst && context.flags.destuctive_os_inst };')


def test_an_unguarded_access_is_refused_at_validation():
    """Cedar will not let a policy silently treat "never ran" as "ran, false"."""
    unguarded = (f'permit (principal, action == {INVOKE}, resource) '
                 'when { context.flags.destuctive_os_inst };')
    result = cedarpy.validate_policies(unguarded, compiled())
    assert not result.validation_passed
    assert "optional" in str(result.errors[0])


def test_the_three_states_stay_distinct():
    schema = compiled()
    assert decide(GUARDED, {"destuctive_os_inst": True}, schema).decision \
        == cedarpy.Decision.Allow                       # ran, fired
    assert decide(GUARDED, {"destuctive_os_inst": False}, schema).decision \
        == cedarpy.Decision.Deny                        # ran, did not fire
    assert decide(GUARDED, {}, schema).decision \
        == cedarpy.Decision.Deny                        # never ran


def test_a_partial_request_is_accepted_without_error():
    """The engine sends only the sensors it ran, which is usually one of 36."""
    result = decide(GUARDED, {"destuctive_os_inst": True}, compiled())
    assert not result.diagnostics.errors


def test_required_attributes_would_have_forced_us_to_lie():
    """The measurement behind the `?` in every generated flag.

    With required attributes a request missing any declared flag is NoDecision,
    so shipping them would mean sending `false` for the 35 sensors that never
    ran -- asserting "the dangerous thing is not happening" about checks nobody
    performed. That is the failure mode this project exists to remove, so it is
    pinned rather than left as a design note.
    """
    required = ag_schema.generate().replace("?: Bool", ": Bool")
    schema = cedarpy.Schema.from_str(required)
    policy = (f'permit (principal, action == {INVOKE}, resource) '
              'when { context.flags.destuctive_os_inst };')
    assert cedarpy.validate_policies(policy, schema).validation_passed

    partial = decide(policy, {"destuctive_os_inst": True}, schema)
    assert partial.decision == cedarpy.Decision.NoDecision
    assert partial.diagnostics.errors

    complete = decide(policy, {f: False for f in sensors.FLAGS} |
                      {"destuctive_os_inst": True}, schema)
    assert complete.decision == cedarpy.Decision.Allow


# ------------------------------------------------------- engine wiring

def test_the_engine_builds_the_shape_the_schema_declares():
    from agentguard import executor                   # noqa: PLC0415

    evaluated = {"destuctive_os_inst": False}
    record = executor.build_request("python_repl", evaluated, ag_schema.RECORD)
    as_set = executor.build_request("python_repl", evaluated, ag_schema.SET)

    assert record["context"]["flags"] == {"destuctive_os_inst": False}
    # the set variant cannot express "ran and said no" at all -- it disappears
    assert as_set["context"]["flags"] == []


def test_the_bundle_reads_its_variant_from_the_generated_schema():
    from agentguard import executor                   # noqa: PLC0415

    assert executor.load_bundle().flags_variant == ag_schema.read_variant()


def test_an_unmarked_schema_stops_the_engine_loading(tmp_path):
    from agentguard import executor                   # noqa: PLC0415

    (tmp_path / "schema.cedarschema").write_text(
        "namespace AgentGuard {\n"
        "  entity Agent = { framework: String };\n"
        "  entity Tool = { kind: String, reversible: Bool };\n"
        '  action invoke appliesTo { principal: [Agent], resource: [Tool],\n'
        "    context: { flags: Set<String> } };\n}\n", encoding="utf-8")
    (tmp_path / "p.cedar").write_text(
        f'@id("x") permit (principal, action == {INVOKE}, resource);', encoding="utf-8")

    with pytest.raises(ValueError, match="regenerate"):
        executor.load_bundle(str(tmp_path))
