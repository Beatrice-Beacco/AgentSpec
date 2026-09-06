"""The advice lattice (plan.md S2.4, thesis §C.4).

S2.4's acceptance is "covers every pair in the lattice", so the join is checked
on all 25 ordered pairs by an independent definition -- position in
`LATTICE` -- rather than by restating the implementation.

The lattice earns its keep only if it is a real meet, so the algebra is checked
too: idempotent, commutative, associative, absorbing. Those four are what make
"the enforcement outcome is independent of the order Cedar lists determining
policies in" a theorem rather than a hope, and that is claim M2.

`substitute` is tested separately and deliberately: it is *not* on the lattice,
and the interesting cases are the ones where it meets something else.
"""
import itertools
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from agentguard import advice                      # noqa: E402

LATTICE = advice.LATTICE
PAIRS = list(itertools.product(LATTICE, repeat=2))


def more_restrictive(a, b):
    """The expected answer, from position in the lattice alone."""
    return a if LATTICE.index(a) <= LATTICE.index(b) else b


# ------------------------------------------------------- S2.4 acceptance

@pytest.mark.parametrize("a,b", PAIRS, ids=[f"{a}+{b}" for a, b in PAIRS])
def test_every_pair_joins_to_the_more_restrictive(a, b):
    """S2.4's acceptance test: all 5 x 5 ordered pairs."""
    assert advice.join([a, b]) == more_restrictive(a, b)


def test_the_lattice_is_the_one_the_thesis_states():
    assert LATTICE == ("stop", "user_inspection", "llm_self_reflect",
                       "skip", "allow")


def test_stop_is_the_bottom_and_allow_the_top():
    assert advice.join(LATTICE) == advice.STOP
    assert advice.join([advice.ALLOW]) == advice.ALLOW
    assert advice.DEFAULT == advice.STOP


# --------------------------------------------------------- the algebra

@pytest.mark.parametrize("a", LATTICE)
def test_idempotent(a):
    assert advice.join([a, a]) == a


@pytest.mark.parametrize("a,b", PAIRS, ids=[f"{a}+{b}" for a, b in PAIRS])
def test_commutative(a, b):
    """The property that makes Cedar's unspecified ordering harmless (M2)."""
    assert advice.join([a, b]) == advice.join([b, a])


@pytest.mark.parametrize("a,b,c", list(itertools.product(LATTICE, repeat=3)),
                         ids=lambda v: v)
def test_associative(a, b, c):
    assert advice.join([advice.join([a, b]), c]) == advice.join([a, advice.join([b, c])])


@pytest.mark.parametrize("a", LATTICE)
def test_stop_absorbs_and_allow_is_the_identity(a):
    assert advice.join([advice.STOP, a]) == advice.STOP
    assert advice.join([advice.ALLOW, a]) == a


def test_join_of_nothing_is_the_safe_end():
    assert advice.join([]) == advice.STOP


def test_an_unknown_value_has_no_rank():
    with pytest.raises(ValueError, match="not on the advice lattice"):
        advice.rank("stopp")


def test_substitute_has_no_rank_and_says_why():
    with pytest.raises(ValueError, match="rewrite"):
        advice.rank(advice.SUBSTITUTE)


# -------------------------------------------------------------- resolve

def contribution(name, advice_value, **annotations):
    return advice.contribution(name, {"id": name, "advice": advice_value,
                                      **annotations})


def test_allow_resolves_to_allow_whatever_the_permits_said():
    """Thesis §C.4 rule 1."""
    result = advice.resolve(True, [contribution("baseline", advice.ALLOW)])
    assert result.advice == advice.ALLOW
    assert not result.substitutes


def test_a_deny_takes_the_join():
    result = advice.resolve(False, [contribution("a", advice.SKIP),
                                    contribution("b", advice.STOP)])
    assert result.advice == advice.STOP
    assert {c.policy for c in result.contributing} == {"a", "b"}


def test_an_unannotated_forbid_contributes_stop():
    """Forgetting @advice must not loosen a decision."""
    assert advice.contribution("policy0", {}).advice == advice.STOP


def test_a_deny_with_no_determining_policy_still_resolves():
    result = advice.resolve(False, [])
    assert result.advice == advice.STOP
    assert "no determining policy" in result.note


def test_an_unrecognised_advice_value_fails_closed_and_says_so():
    """Reaching here means the policy set skipped tools/validate_policies.py.

    Resolution is total on purpose: raising would put an exception between the
    agent and its guard at the moment the guard matters most.
    """
    result = advice.resolve(False, [contribution("typo", "stopp")])
    assert result.advice == advice.STOP
    assert "stopp" in result.note


# ----------------------------------------------------------- substitute

SUBSTITUTING = {"substitute_tool": "safe_tool", "substitute_args": '{"cmd": "ls"}'}


def test_a_lone_substitution_applies():
    result = advice.resolve(False, [contribution("rewrite", advice.SUBSTITUTE,
                                                 **SUBSTITUTING)])
    assert result.advice == advice.SUBSTITUTE
    assert result.substitutes
    assert result.substitution.tool == "safe_tool"
    assert "safe_tool" in str(result.substitution)


@pytest.mark.parametrize("other", LATTICE, ids=list(LATTICE))
def test_a_substitution_meeting_anything_else_falls_back_to_stop(other):
    """The rule the plan asks to be stated and justified.

    A rewrite invokes a tool, so it is not a degree of restriction and has no
    place on the lattice -- there is no honest meet with `skip` or `stop`.
    Taking the join of the *others* instead would silently discard the rewrite
    the author asked for, and would make the outcome depend on which other
    policies happened to fire: the composition sensitivity the lattice exists to
    remove. `stop` is the only outcome at least as safe as every alternative.
    """
    result = advice.resolve(False, [
        contribution("rewrite", advice.SUBSTITUTE, **SUBSTITUTING),
        contribution("other", other),
    ])
    assert result.advice == advice.STOP
    assert not result.substitutes
    assert "unique determining policy" in result.note


def test_two_substitutions_also_fall_back():
    """Two rewrites of the same call have no meet either -- which one wins?"""
    result = advice.resolve(False, [
        contribution("a", advice.SUBSTITUTE, **SUBSTITUTING),
        contribution("b", advice.SUBSTITUTE, substitute_tool="other_tool"),
    ])
    assert result.advice == advice.STOP
    assert not result.substitutes


def test_a_substitution_with_nothing_to_substitute_falls_back():
    result = advice.resolve(False, [contribution("rewrite", advice.SUBSTITUTE)])
    assert result.advice == advice.STOP
    assert "substitute_tool" in result.note


def test_substitute_is_a_legal_advice_value_but_not_a_lattice_element():
    assert advice.SUBSTITUTE in advice.VALUES
    assert advice.SUBSTITUTE not in advice.LATTICE


# ------------------------------------------------- one definition only

def test_the_validator_lints_against_this_module():
    """The lattice was duplicated in tools/ until S2.4. It must not be again."""
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    import validate_policies as vp                  # noqa: PLC0415

    assert vp.ag_advice is advice


def test_the_executor_resolves_through_this_module():
    from agentguard import executor                 # noqa: PLC0415

    assert executor.ADVICE_LATTICE == list(advice.LATTICE)
    assert executor.DEFAULT_ADVICE == advice.DEFAULT
    assert set(executor.ADVICE_TO_ENFORCEMENT) == set(advice.LATTICE)


def test_every_lattice_outcome_maps_to_an_enforcement_class():
    """A lattice element with nothing to apply it with would be decoration."""
    from enforcement import ENFORCEMENT_TO_CLASS     # noqa: PLC0415
    from agentguard import executor                  # noqa: PLC0415

    for outcome in advice.LATTICE:
        assert executor.ADVICE_TO_ENFORCEMENT[outcome] in ENFORCEMENT_TO_CLASS


def test_substitute_has_no_enforcement_class_yet():
    """Deliberate, and the reason is a finding: AgentSpec's InvokeAction is
    unregistered and a no-op (docs/findings.md D-5), so S2.6 has to implement
    the rewrite rather than delegate to it."""
    from agentguard import executor                  # noqa: PLC0415

    assert advice.SUBSTITUTE not in executor.ADVICE_TO_ENFORCEMENT
