"""The Cedar spikes must keep passing, or their findings are stale.

docs/spikes.md records decisions the whole Sprint 2 design rests on -- notably
that @advice is reachable via policies_to_json_str() and not via
id_annotations_by_reason. If a cedarpy upgrade changes either, that has to fail
here rather than be discovered halfway through building the engine.
"""
import json
import os
import sys

import pytest

SPIKES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spikes")
if SPIKES not in sys.path:
    sys.path.insert(0, SPIKES)

cedarpy = pytest.importorskip("cedarpy")

import annotations as ann                      # noqa: E402
import hello_cedar                             # noqa: E402
import latency                                 # noqa: E402
import validation                              # noqa: E402


# ----------------------------------------------------------------- S1.1

def test_hello_cedar_reaches_both_decisions():
    assert hello_cedar.main() == 0


def test_benign_action_is_allowed():
    result = hello_cedar.decide([])
    assert result.decision == cedarpy.Decision.Allow
    assert not result.diagnostics.errors


def test_flagged_action_is_denied_by_the_forbid():
    result = hello_cedar.decide(["destuctive_os_inst"])
    assert result.decision == cedarpy.Decision.Deny
    named = result.diagnostics.id_annotations_by_reason.values()
    assert "no_destructive_os_call" in named


# ----------------------------------------------------------------- S1.2

def test_annotations_spike_passes():
    assert ann.main() == 0


def test_id_annotations_by_reason_carries_only_id():
    """The plan's first choice, recorded as insufficient rather than assumed so.

    If a future cedarpy starts returning full annotations here, this fails and
    docs/spikes.md needs revisiting -- the fallback would no longer be needed.
    """
    result = ann.decide(["involve_system_file"])
    values = list(result.diagnostics.id_annotations_by_reason.values())
    assert values == ["inspect_system_file_copy"]
    assert "user_inspection" not in values


def test_policies_to_json_str_carries_every_annotation():
    table = ann.annotation_table(ann.POLICIES)
    entry = next(a for a in table.values() if a.get("id") == "inspect_system_file_copy")
    assert entry["advice"] == "user_inspection"
    assert entry["source"] == "agentspec:pythonrepl.ar#index4"


def test_annotation_ids_match_diagnostics_reasons():
    """The join the whole advice design depends on."""
    table = ann.annotation_table(ann.POLICIES)
    reasons = ann.decide(["submit_post_request"]).diagnostics.reasons
    assert reasons and all(pid in table for pid in reasons)


@pytest.mark.parametrize("flags,expected", [
    ([], "allow"),
    (["involve_system_file"], "user_inspection"),
    (["submit_post_request"], "stop"),
    (["involve_system_file", "submit_post_request"], "stop"),
])
def test_advice_lattice_takes_the_most_restrictive(flags, expected):
    table = ann.annotation_table(ann.POLICIES)
    advice, _ = ann.resolve(ann.decide(flags), table)
    assert advice == expected


def test_resolution_does_not_depend_on_policy_order():
    """Cedar does not return determining policies in source order.

    Reversing the policy text must not change the outcome. This is the property
    AgentSpec lacks (ui/examples.py example 8) and the reason for the lattice.
    """
    table = ann.annotation_table(ann.POLICIES)
    both = ["involve_system_file", "submit_post_request"]
    baseline, _ = ann.resolve(ann.decide(both), table)

    chunks = ann.POLICIES.strip().split("\n\n")
    reversed_policies = "\n\n".join(reversed(chunks))
    result = cedarpy.is_authorized({
        "principal": 'Agent::"a1"', "action": 'Action::"invoke"',
        "resource": 'Tool::"python_repl"', "context": {"flags": both},
    }, reversed_policies, [])
    flipped, _ = ann.resolve(result, ann.annotation_table(reversed_policies))

    assert flipped == baseline == "stop"


def test_unannotated_forbid_defaults_to_stop():
    """Missing @advice must land on the safe end of the lattice, not the loose one."""
    policies = 'forbid (principal, action, resource) when { context.flags.contains("x") };'
    result = cedarpy.is_authorized({
        "principal": 'Agent::"a"', "action": 'Action::"invoke"',
        "resource": 'Tool::"t"', "context": {"flags": ["x"]},
    }, policies, [])
    table = {pid: body.get("annotations", {}) for pid, body
             in json.loads(cedarpy.policies_to_json_str(policies))["staticPolicies"].items()}
    assert ann.resolve(result, table)[0] == "stop"


# ----------------------------------------------------------------- S1.3

def test_validation_spike_passes():
    assert validation.main() == 0


@pytest.mark.parametrize(
    "label,schema,policy,must_be_caught",
    validation.CASES,
    ids=[c[0] for c in validation.CASES],
)
def test_validator_behaves_as_documented(label, schema, policy, must_be_caught):
    """Each row of docs/spikes.md S1.3, asserted rather than described."""
    result = cedarpy.validate_policies(policy, cedarpy.Schema.from_str(schema))
    assert (not result.validation_passed) == must_be_caught


def test_set_of_strings_cannot_catch_a_misspelled_flag():
    """The negative half of the S2.2 decision.

    If a future Cedar starts catching this, the record-of-Bools codegen in S2.2
    becomes unnecessary -- so the miss is pinned, not just noted.
    """
    policy = ('permit(principal, action == Action::"invoke", resource) '
              'when { context.flags.contains("involve_system_fyle") };')
    result = cedarpy.validate_policies(policy, cedarpy.Schema.from_str(validation.SCHEMA_SET))
    assert result.validation_passed


def test_record_of_bools_catches_the_same_misspelled_flag():
    policy = ('permit(principal, action == Action::"invoke", resource) '
              'when { context.flags.involve_system_fyle };')
    result = cedarpy.validate_policies(policy, cedarpy.Schema.from_str(validation.SCHEMA_RECORD))
    assert not result.validation_passed
    assert "involve_system_fyle" in str(result.errors[0])


# ----------------------------------------------------------------- S1.4

def test_policyset_and_policy_text_agree():
    """Pre-parsing must be a pure optimisation, not a change in behaviour.

    No timing is asserted -- CI runners are too noisy for that. The measured
    numbers live in docs/spikes.md; what has to hold here is equivalence.
    """
    from_text = cedarpy.is_authorized(latency.REQUEST, latency.POLICIES, latency.ENTITIES)
    from_set = cedarpy.is_authorized(latency.REQUEST,
                                     cedarpy.PolicySet.from_str(latency.POLICIES),
                                     latency.ENTITIES)
    assert from_text.decision == from_set.decision == cedarpy.Decision.Deny
    assert sorted(from_text.diagnostics.reasons) == sorted(from_set.diagnostics.reasons)


def test_latency_spike_request_validates_against_its_schema():
    """The spike measures a request that is actually schema-valid."""
    result = cedarpy.is_authorized(latency.REQUEST, latency.POLICIES, latency.ENTITIES,
                                   cedarpy.Schema.from_str(latency.SCHEMA))
    assert not result.diagnostics.errors
    assert cedarpy.validate_policies(
        latency.POLICIES, cedarpy.Schema.from_str(latency.SCHEMA)).validation_passed
