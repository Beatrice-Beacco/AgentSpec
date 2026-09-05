"""policies/schema.cedarschema must actually validate policies (plan.md S1.5).

The schema is the whole reason the Cedar half of the system is checkable, so
these tests assert three things:

  1. it parses, and a hand-written policy validates against it  -- S1.5's
     acceptance test;
  2. the mistakes it is supposed to catch are caught -- the same classes
     docs/spikes.md S1.3 measured, but against the real file rather than a
     spike's inline string;
  3. the one class it is known *not* to catch is still not caught, so the S2.2
     decision to regenerate `flags` as a record of Bools stays evidence-backed
     rather than assumed.
"""
import os
import sys

import pytest

cedarpy = pytest.importorskip("cedarpy")

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import validate_policies as vp                  # noqa: E402


INVOKE = 'AgentGuard::Action::"invoke"'

# The hand-written policy of S1.5's acceptance test: one baseline permit, one
# forbid keyed on a materialised predicate. Deliberately not read from
# policies/core.cedar -- that file arrives in S1.6, and this test has to be able
# to fail on the schema alone.
HAND_WRITTEN = f"""
@id("baseline_allow_tools")
permit (principal, action == {INVOKE}, resource);

@id("no_destructive_os_call")
@advice("stop")
forbid (
  principal,
  action   == {INVOKE},
  resource == AgentGuard::Tool::"python_repl"
)
when {{ context.flags.contains("destuctive_os_inst") }};
"""


@pytest.fixture(scope="module")
def schema():
    return vp.load_schema()


def validate(policy, schema):
    return cedarpy.validate_policies(policy, schema)


# ------------------------------------------------------------------ S1.5

def test_schema_file_parses(schema):
    assert schema is not None


def test_hand_written_policy_validates(schema):
    """S1.5's acceptance test."""
    result = validate(HAND_WRITTEN, schema)
    assert result.validation_passed, [str(e) for e in result.errors]


def test_the_schema_actually_decides(schema):
    """A schema that validates but cannot reach both verdicts proves nothing."""
    request = {
        "principal": 'AgentGuard::Agent::"a1"',
        "action": INVOKE,
        "resource": 'AgentGuard::Tool::"python_repl"',
        "context": {"flags": ["destuctive_os_inst"]},
    }
    entities = [
        {"uid": {"type": "AgentGuard::Agent", "id": "a1"},
         "attrs": {"framework": "langchain"}, "parents": []},
        {"uid": {"type": "AgentGuard::Tool", "id": "python_repl"},
         "attrs": {"kind": "code_exec", "reversible": False}, "parents": []},
    ]
    denied = cedarpy.is_authorized(request, HAND_WRITTEN, entities, schema)
    allowed = cedarpy.is_authorized({**request, "context": {"flags": []}},
                                    HAND_WRITTEN, entities, schema)

    assert denied.decision == cedarpy.Decision.Deny
    assert allowed.decision == cedarpy.Decision.Allow
    assert not denied.diagnostics.errors and not allowed.diagnostics.errors


# --------------------------------------------------- what it must catch

@pytest.mark.parametrize("label,policy", [
    ("typo in a context attribute",
     f'permit (principal, action == {INVOKE}, resource) when {{ context.flgs.contains("x") }};'),
    ("typo in an entity attribute",
     f'permit (principal, action == {INVOKE}, resource) when {{ resource.kindd == "code_exec" }};'),
    ("type mismatch on an entity attribute",
     f'permit (principal, action == {INVOKE}, resource) when {{ resource.reversible == "yes" }};'),
    ("entity type not in the schema",
     f'permit (principal, action == {INVOKE}, resource == AgentGuard::Widget::"w");'),
    ("action not in the schema",
     'permit (principal, action == AgentGuard::Action::"delete", resource);'),
    ("principal type the action does not apply to",
     f'permit (principal == AgentGuard::Tool::"t", action == {INVOKE}, resource);'),
])
def test_malformed_policies_are_rejected(label, policy, schema):
    result = validate(policy, schema)
    assert not result.validation_passed, f"{label} was accepted"


def test_unnamespaced_action_is_rejected(schema):
    """A cheap mistake worth pinning: the namespace is not optional in policies."""
    result = validate('permit (principal, action == Action::"invoke", resource);', schema)
    assert not result.validation_passed


# --------------------------------------------------- what it cannot catch

def test_a_misspelled_flag_is_not_caught(schema):
    """The known hole in `flags: Set<String>`, and the reason S2.2 exists.

    Any string is a valid set member, so this policy type-checks and then
    silently never fires -- the exact failure mode tests/test_fail_open.py
    documents for AgentSpec. When S2.2 regenerates `flags` as a record of named
    Bools this must start failing; that is the signal to delete this test and
    move the row in docs/spikes.md from "MISSED" to "caught".
    """
    policy = (f'permit (principal, action == {INVOKE}, resource) '
              'when { context.flags.contains("destuctive_os_inzt") };')
    assert validate(policy, schema).validation_passed


# ------------------------------------------------------ the tool itself

def test_validator_reports_success_on_the_hand_written_policy(tmp_path, schema):
    path = tmp_path / "hand_written.cedar"
    path.write_text(HAND_WRITTEN, encoding="utf-8")
    ok, messages = vp.check(str(path), schema)
    assert ok and messages == []


def test_validator_exits_nonzero_on_a_bad_policy(tmp_path, schema):
    path = tmp_path / "broken.cedar"
    path.write_text(f'permit (principal, action == {INVOKE}, resource) '
                    'when { context.flgs.contains("x") };', encoding="utf-8")
    assert vp.main([str(path)]) == 1


def test_validator_accepts_the_shipped_policy_tree():
    """Whatever is in policies/ must validate -- from S1.6 on, that is core.cedar."""
    assert vp.main([]) == 0
