"""policies/core.cedar -- the walking skeleton's policy set (plan.md S1.6).

Two policies: a baseline permit and a forbid keyed on `destuctive_os_inst`
carrying `@advice("stop")`. What has to hold before S1.7 can wire them into the
executor:

  * both verdicts are reachable, on the real file rather than an inline string;
  * the enforcement outcome survives the trip out of Cedar -- Deny alone is not
    enough, since AgentSpec has five outcomes and the executor needs to know
    which one;
  * the annotation lint in tools/validate_policies.py actually rejects the
    annotation mistakes Cedar's own validator ignores.
"""
import json
import os
import sys

import pytest

cedarpy = pytest.importorskip("cedarpy")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO_ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import validate_policies as vp                  # noqa: E402

CORE = os.path.join(REPO_ROOT, "policies", "core.cedar")
INVOKE = 'AgentGuard::Action::"invoke"'

ENTITIES = [
    {"uid": {"type": "AgentGuard::Agent", "id": "a1"},
     "attrs": {"framework": "langchain"}, "parents": []},
    {"uid": {"type": "AgentGuard::Tool", "id": "python_repl"},
     "attrs": {"kind": "code_exec", "reversible": False}, "parents": []},
]


@pytest.fixture(scope="module")
def policies():
    with open(CORE, encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def schema():
    return vp.load_schema()


def decide(policies, flags, tool="python_repl", schema=None):
    return cedarpy.is_authorized({
        "principal": 'AgentGuard::Agent::"a1"',
        "action": INVOKE,
        "resource": f'AgentGuard::Tool::"{tool}"',
        "context": {"flags": list(flags)},
    }, policies, ENTITIES, schema)


def advice_table(policies):
    """policy id -> annotations, via cedarpy's own parser (docs/spikes.md S1.2)."""
    parsed = json.loads(cedarpy.policies_to_json_str(policies))
    return {pid: body.get("annotations", {})
            for pid, body in parsed["staticPolicies"].items()}


# ------------------------------------------------------------- the file

def test_core_validates_against_the_schema(policies, schema):
    result = cedarpy.validate_policies(policies, schema)
    assert result.validation_passed, [str(e) for e in result.errors]


def test_core_has_exactly_the_two_policies_the_step_asks_for(policies):
    table = advice_table(policies)
    assert sorted(a["id"] for a in table.values()) == [
        "baseline_allow_tools", "no_destructive_os_call"
    ]


# ---------------------------------------------------------- both verdicts

def test_destructive_call_is_denied(policies, schema):
    result = decide(policies, ["destuctive_os_inst"], schema=schema)
    assert result.decision == cedarpy.Decision.Deny
    assert not result.diagnostics.errors
    named = result.diagnostics.id_annotations_by_reason.values()
    assert "no_destructive_os_call" in named


def test_benign_call_is_allowed(policies, schema):
    """The false-positive guard. A policy set that denies everything passes the
    test above and is worthless."""
    result = decide(policies, [], schema=schema)
    assert result.decision == cedarpy.Decision.Allow
    assert not result.diagnostics.errors


def test_the_forbid_is_scoped_to_the_python_repl(policies, schema):
    """`trigger PythonREPL` is a resource constraint, not a global condition."""
    result = decide(policies, ["destuctive_os_inst"], tool="shell", schema=None)
    assert result.decision == cedarpy.Decision.Allow


# ------------------------------------------------------- advice survives

def test_the_deny_carries_its_enforcement_outcome(policies):
    """Deny alone is not actionable: the executor needs one of five outcomes."""
    result = decide(policies, ["destuctive_os_inst"])
    table = advice_table(policies)
    advice = {table[pid].get("advice", "stop") for pid in result.diagnostics.reasons}
    assert advice == {"stop"}


def test_the_baseline_permit_carries_no_advice(policies):
    """@advice on a permit would be silently ignored, so it must not be there."""
    table = advice_table(policies)
    baseline = next(a for a in table.values() if a["id"] == "baseline_allow_tools")
    assert "advice" not in baseline


def test_every_policy_is_traceable_to_a_source(policies):
    """A denying policy has to say which AgentSpec rule it came from."""
    table = advice_table(policies)
    denying = next(a for a in table.values() if a["id"] == "no_destructive_os_call")
    assert denying["source"].startswith("agentspec:")


# ----------------------------------------------------- the annotation lint

def test_lint_accepts_core(policies):
    assert vp.annotation_errors(policies) == []


@pytest.mark.parametrize("label,policy,fragment", [
    ("advice that is not on the lattice",
     f'@id("x") @advice("stopp") forbid (principal, action == {INVOKE}, resource);',
     "not an enforcement outcome"),
    ("no @id at all",
     f'forbid (principal, action == {INVOKE}, resource);',
     "no @id"),
    ("advice on a permit",
     f'@id("x") @advice("stop") permit (principal, action == {INVOKE}, resource);',
     "has no effect"),
])
def test_lint_rejects_what_cedar_ignores(label, policy, fragment, schema):
    """Cedar treats annotations as opaque strings, so these all *validate*."""
    assert cedarpy.validate_policies(policy, schema).validation_passed, label
    errors = vp.annotation_errors(policy)
    assert any(fragment in e for e in errors), (label, errors)


def test_an_unannotated_forbid_is_allowed_through_the_lint():
    """Missing @advice defaults to `stop` at resolution time, which is safe."""
    policy = f'@id("x") forbid (principal, action == {INVOKE}, resource);'
    assert vp.annotation_errors(policy) == []
