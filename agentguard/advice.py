"""The advice lattice (plan.md S2.4, thesis §C.4 -- contribution M2).

Cedar answers Allow or Deny. AgentSpec has five enforcement outcomes, and a
single decision can be determined by several policies at once, each carrying
different `@advice`. Something has to turn that set into exactly one outcome,
deterministically. That is this module.

                stop                (most restrictive)
                 |
          user_inspection
                 |
          llm_self_reflect
                 |
               skip
                 |
               allow                (least restrictive)

The join takes the most restrictive. It exists because **Cedar does not return
determining policies in source order** -- docs/spikes.md S1.2 saw
`['policy2', 'policy1']` for a two-forbid decision -- so anything that read "the
first determining policy" would be reading an unspecified ordering. The join
makes ordering irrelevant by construction, which is precisely the property
AgentSpec's `for rule in self.rules: ... return` loop lacks (its `skip` before
`stop` gives SKIPPED and the reverse gives STOPPED; ui/examples.py example 8).
S2.8 turns that into a property test.

`substitute` is deliberately **not on the lattice**
--------------------------------------------------
A rewrite is not a degree of restriction. `invoke_action(t, {...})` replaces the
proposed call with a different one, so it *invokes a tool* -- it can be more
dangerous than what it replaced, not less. There is no honest place to slot it
between `skip` and `stop`, so it has no rank, and combining it with anything is
undefined.

The rule, therefore: a substitution applies only when it is the **unique**
determining policy. Otherwise the outcome is `stop`. Not the join of the other
policies -- that would silently discard the substitution's intent (the author
asked for a rewrite and got a suppression) and would make the result depend on
which other policies happened to fire, reintroducing exactly the composition
sensitivity the lattice removes. `stop` is the one outcome that is at least as
safe as every alternative and does not pretend to have honoured the rewrite.

⚠️ Note for the write-up: **substitution is unreachable in the baseline**, so
there is nothing to compare against. AgentSpec's grammar accepts
`invoke_action(...)`, `Rule.from_text` parses it, and then
`ENFORCEMENT_TO_CLASS[...]` raises KeyError mid-run because `InvokeAction` is
never registered -- and it is a no-op even so, returning the *original* action
unchanged. No rule in the shipped corpus uses it. See docs/findings.md D-5. Any
claim about substitution is a claim about a capability we added, not one we
improved.
"""
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence, Tuple

STOP = "stop"
USER_INSPECTION = "user_inspection"
LLM_SELF_REFLECT = "llm_self_reflect"
SKIP = "skip"
ALLOW = "allow"

#: Most restrictive first. Index in this tuple *is* the rank.
LATTICE: Tuple[str, ...] = (STOP, USER_INSPECTION, LLM_SELF_REFLECT, SKIP, ALLOW)

#: A rewrite rather than a degree of restriction; see the module docstring.
SUBSTITUTE = "substitute"

#: Everything `@advice` may legally name.
VALUES: Tuple[str, ...] = LATTICE + (SUBSTITUTE,)

#: What an unannotated `forbid` means, and where anything unresolvable lands.
DEFAULT = STOP

#: Annotations a substituting policy must carry.
TOOL_ANNOTATION = "substitute_tool"
ARGS_ANNOTATION = "substitute_args"


def rank(advice: str) -> int:
    """Position on the lattice; lower is more restrictive."""
    try:
        return LATTICE.index(advice)
    except ValueError:
        raise ValueError(
            f"{advice!r} is not on the advice lattice "
            f"({', '.join(LATTICE)})"
            + (" -- substitute is a rewrite and has no rank" if advice == SUBSTITUTE else "")
        ) from None


def join(values: Iterable[str]) -> str:
    """The most restrictive of several advice values.

    Order-independent, idempotent, associative -- it is a meet on a total order,
    which is what makes the enforcement outcome independent of the order Cedar
    happens to list determining policies in.
    """
    values = list(values)
    if not values:
        return DEFAULT
    return min(values, key=rank)


@dataclass(frozen=True)
class Substitution:
    """The rewrite a `substitute` policy asks for."""
    tool: str
    args: str = ""

    def __str__(self):
        return f"invoke_action({self.tool}, {self.args or '{}'})"


@dataclass(frozen=True)
class Contribution:
    """One determining policy's contribution to the outcome."""
    policy: str
    advice: str
    substitution: Optional[Substitution] = None

    def __str__(self):
        return f"@{self.policy}={self.advice}"


@dataclass(frozen=True)
class Resolution:
    """One enforcement outcome, plus why it is that one."""
    advice: str
    contributing: Tuple[Contribution, ...] = ()
    substitution: Optional[Substitution] = None
    #: Set only when the outcome is not simply the join -- a downgraded
    #: substitution, an unknown advice value, a Deny with no determining policy.
    note: str = ""

    @property
    def substitutes(self) -> bool:
        return self.substitution is not None


def contribution(policy_id: str, annotations: Mapping[str, str]) -> Contribution:
    """Read one policy's annotations into a Contribution.

    An unannotated policy contributes `stop`: the safe end, so forgetting
    `@advice` cannot loosen a decision.
    """
    advice = annotations.get("advice", DEFAULT)
    substitution = None
    if advice == SUBSTITUTE and annotations.get(TOOL_ANNOTATION):
        substitution = Substitution(tool=annotations[TOOL_ANNOTATION],
                                    args=annotations.get(ARGS_ANNOTATION, ""))
    return Contribution(policy=annotations.get("id", policy_id),
                        advice=advice, substitution=substitution)


def resolve(allow: bool, contributions: Sequence[Contribution]) -> Resolution:
    """Decision + determining policies -> exactly one enforcement outcome.

    Total: every input produces a Resolution, and anything it cannot make sense
    of resolves to `stop`. Raising here would put an exception between the agent
    and its guard at the moment the guard matters most.
    """
    contributions = tuple(contributions)

    if allow:
        # Thesis §C.4 rule 1: an Allow is `allow`, whatever the permits say.
        return Resolution(advice=ALLOW, contributing=contributions)

    if not contributions:
        return Resolution(advice=DEFAULT, note="denied with no determining policy")

    unknown = [c for c in contributions if c.advice not in VALUES]
    if unknown:
        # tools/validate_policies.py rejects these at load, so reaching here
        # means the policy set was not validated. Fail closed and say so.
        return Resolution(
            advice=DEFAULT, contributing=contributions,
            note="unrecognised advice: " + ", ".join(sorted(c.advice for c in unknown)))

    rewrites = [c for c in contributions if c.advice == SUBSTITUTE]
    if rewrites:
        if len(contributions) > 1:
            return Resolution(
                advice=STOP, contributing=contributions,
                note=("substitution applies only as the unique determining policy; "
                      f"{len(contributions)} policies determined this decision"))
        if rewrites[0].substitution is None:
            return Resolution(
                advice=STOP, contributing=contributions,
                note=f"@advice(\"{SUBSTITUTE}\") without @{TOOL_ANNOTATION}")
        return Resolution(advice=SUBSTITUTE, contributing=contributions,
                          substitution=rewrites[0].substitution)

    return Resolution(advice=join(c.advice for c in contributions),
                      contributing=contributions)
