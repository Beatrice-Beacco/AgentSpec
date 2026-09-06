"""Order independence (plan.md S2.8, thesis claim M2).

The property: **the enforcement outcome does not depend on the order the
policies were written in.** It is what lets a policy set be reasoned about as a
set rather than as a program, and it is the concrete difference between a
policy engine and AgentSpec's `for rule in self.rules: ... return` loop.

Both halves are run here, because the claim is comparative:

  * Cedar + the advice lattice: shuffle the policy set 100 times, and the
    decision, the resolved outcome and the set of determining policies are all
    identical every time.
  * AgentSpec: enumerate *all* permutations of an equivalent rule list and
    watch the verdict change.

The Cedar half goes through `engine.load()` on disk for every shuffle, not
through a shortcut, so the synthetic policy ids ("policy0", "policy1", ...) are
reassigned by position each time -- which is exactly the thing that could break
if the resolution keyed on them.

`tests/test_advice.py` proves the join is a meet on a total order
(commutative, associative, idempotent). That is *why* this holds. This file
checks that the engine actually inherits it.
"""
import itertools
import os
import random
import sys

import pytest

cedarpy = pytest.importorskip("cedarpy")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from conftest import DESTRUCTIVE_INPUT, TOOL_NAME, react_script, show  # noqa: E402

from agentguard import advice as ag_advice        # noqa: E402
from agentguard import engine                     # noqa: E402
from agentguard import schema as ag_schema        # noqa: E402
from agent import Action                          # noqa: E402
from state import RuleState                       # noqa: E402

INVOKE = 'AgentGuard::Action::"invoke"'
FIRES = ("context.flags has destuctive_os_inst && "
         "context.flags.destuctive_os_inst")

BASELINE = f'@id("baseline") permit (principal, action == {INVOKE}, resource);'

#: Three policies that all deny the same action with different advice. Their
#: join is `stop` -- the most restrictive -- whichever order they appear in.
POLICIES = [
    f'@id("suppress") @advice("skip") forbid (principal, action == {INVOKE}, '
    f'resource) when {{ {FIRES} }};',
    f'@id("halt") @advice("stop") forbid (principal, action == {INVOKE}, '
    f'resource) when {{ {FIRES} }};',
    f'@id("ask") @advice("user_inspection") forbid (principal, action == {INVOKE}, '
    f'resource) when {{ {FIRES} }};',
]

SHUFFLES = 100


def state_for(tool_input=DESTRUCTIVE_INPUT):
    from langchain_core.agents import AgentAction          # noqa: PLC0415
    action = Action.from_langchain(
        AgentAction(tool=TOOL_NAME, tool_input=tool_input, log=""))
    return RuleState(action=action, agent=None, intermediate_steps=[],
                     user_input="Delete the unimportant txt file")


def decide_with(order, tmp_path):
    """Write the policies in this order, load them for real, and decide."""
    (tmp_path / "schema.cedarschema").write_text(ag_schema.generate(),
                                                 encoding="utf-8")
    (tmp_path / "core.cedar").write_text("\n\n".join(order), encoding="utf-8")
    engine.load.cache_clear()
    verdict = engine.decide(engine.load(str(tmp_path)), state_for())
    engine.load.cache_clear()
    return verdict


def outcome_of(verdict):
    """Everything a caller could observe, normalised away from policy ids.

    The synthetic ids are positional, so comparing them directly would be
    comparing the shuffle to itself. What must be stable is the *decision*, the
    *resolved advice*, and *which named policies* determined it.
    """
    return (
        verdict.decision,
        verdict.advice,
        frozenset(c.policy for c in verdict.resolution.contributing),
    )


# ------------------------------------------------------------ Cedar: stable

def test_the_verdict_survives_a_hundred_shuffles(tmp_path):
    """S2.8's acceptance test."""
    order = [BASELINE] + POLICIES
    expected = outcome_of(decide_with(order, tmp_path))

    rng = random.Random(20260906)
    seen = {expected}
    for _ in range(SHUFFLES):
        shuffled = list(order)
        rng.shuffle(shuffled)
        seen.add(outcome_of(decide_with(shuffled, tmp_path)))

    assert len(seen) == 1, f"{len(seen)} distinct outcomes across {SHUFFLES} shuffles"
    assert expected[0] == "Deny"
    assert expected[1] == ag_advice.STOP
    assert expected[2] == {"suppress", "halt", "ask"}


def test_every_permutation_gives_the_same_outcome(tmp_path):
    """The exhaustive version: 4 policies, all 24 orderings."""
    outcomes = {outcome_of(decide_with(list(order), tmp_path))
                for order in itertools.permutations([BASELINE] + POLICIES)}

    assert len(outcomes) == 1


def test_the_join_is_the_most_restrictive_not_the_first_listed(tmp_path):
    """`skip` first would win under a first-match loop; the join gives `stop`."""
    verdict = decide_with([BASELINE] + POLICIES, tmp_path)

    assert verdict.advice == ag_advice.STOP
    assert ag_advice.rank(ag_advice.STOP) < ag_advice.rank(ag_advice.SKIP)


def test_cedar_still_does_not_list_determining_policies_in_source_order(tmp_path):
    """The reason the join exists at all (docs/spikes.md S1.2).

    If Cedar listed them in source order, "take the first" would be a defensible
    (if fragile) design. It does not, so it never was.
    """
    verdict = decide_with([BASELINE] + POLICIES, tmp_path)
    ids = list(verdict.policy_ids)

    assert len(ids) == 3
    assert ids != sorted(ids), (
        "Cedar happened to return source order this time; the property under "
        "test is unaffected, but the claim in docs/spikes.md needs re-checking")


# ------------------------------------------------- sensors: also independent

def test_the_flags_do_not_depend_on_the_order_sensors_ran(monkeypatch):
    """Thesis §C.4 claims independence of sensor order as well as policy order.

    Cheap to check and worth pinning: it would stop holding the moment a sensor
    acquired a side effect that another one could observe.
    """
    from agentguard import request as ag_request             # noqa: PLC0415
    from agentguard import sensors                           # noqa: PLC0415

    baseline = ag_request.materialise(state_for()).evaluated
    rng = random.Random(7)

    for _ in range(20):
        shuffled = list(sensors.by_domain(sensors.CODE))
        rng.shuffle(shuffled)
        monkeypatch.setattr(ag_request, "select",
                            lambda *_a, **_k: tuple(shuffled))
        assert ag_request.materialise(state_for()).evaluated == baseline


# --------------------------------------------------- AgentSpec: not stable

def rule_text(name, enforce):
    return (f"rule @{name}\ntrigger\n    {TOOL_NAME}\n"
            f"check\n    true\nenforce\n    {enforce}\nend\n")


#: The legacy equivalent: three rules that all trigger, with different
#: enforcement. `none` returns CONTINUE, so the loop moves on to the next rule.
LEGACY_RULES = {
    "suppress": rule_text("suppress", "skip"),
    "halt": rule_text("halt", "stop"),
    "pass": rule_text("pass", "none"),
}


def legacy_verdict(order, agent_factory, tool_calls):
    tool_calls.clear()
    agent = agent_factory([LEGACY_RULES[name] for name in order],
                          react_script(DESTRUCTIVE_INPUT, "42"))
    result = agent.invoke("Delete the unimportant txt file")
    if "stopped by" in result["output"]:
        return "STOPPED"
    if not tool_calls:
        return "SKIPPED"
    return "ALLOWED"


@pytest.mark.legacy_only(
    "the counterexample *is* the legacy engine's rule-list ordering")
def test_agentspec_changes_its_verdict_when_the_rules_are_reordered(
        agent_factory, tool_calls):
    """The counterexample, enumerated rather than asserted once.

    Every ordering of the same three rules, and the verdict each produces. This
    is the table in docs/findings.md.
    """
    verdicts = {order: legacy_verdict(order, agent_factory, tool_calls)
                for order in itertools.permutations(LEGACY_RULES)}

    assert len(set(verdicts.values())) > 1, (
        "expected the legacy engine to disagree with itself; it did not")
    assert verdicts[("suppress", "halt", "pass")] == "SKIPPED"
    assert verdicts[("halt", "suppress", "pass")] == "STOPPED"
    # `none` continues, so it never decides -- the first *deciding* rule wins
    assert verdicts[("pass", "suppress", "halt")] == "SKIPPED"
    assert verdicts[("pass", "halt", "suppress")] == "STOPPED"


@pytest.mark.legacy_only(
    "the counterexample *is* the legacy engine's rule-list ordering")
def test_the_two_engines_disagree_about_the_same_reordering(
        agent_factory, tool_calls, tmp_path):
    """Side by side: one input, two orderings, two engines.

    AgentSpec returns a different outcome for the two orderings. AgentGuard
    returns the same one, and it is the more restrictive of the two -- which is
    the outcome a reader of either ordering would want.
    """
    legacy_first = legacy_verdict(("suppress", "halt", "pass"),
                                  agent_factory, tool_calls)
    legacy_second = legacy_verdict(("halt", "suppress", "pass"),
                                   agent_factory, tool_calls)
    assert legacy_first != legacy_second

    cedar_first = decide_with([BASELINE] + POLICIES, tmp_path).advice
    cedar_second = decide_with([BASELINE] + list(reversed(POLICIES)),
                               tmp_path).advice
    assert cedar_first == cedar_second == ag_advice.STOP
