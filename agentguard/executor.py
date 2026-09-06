"""The walking skeleton: Cedar makes the decision (plan.md S1.7).

`CedarControlledAgentExecutor` overrides exactly one method of AgentSpec's
`ControlledAgentExecutor` -- `validate_and_enforce` -- and replaces the
rule-by-rule loop with the pipeline from thesis §C.1:

    sensors  ->  request  ->  Cedar  ->  advice  ->  enforcement.py

Everything else (the ReAct loop, the enforcement classes, the observation text
fed back to the agent) is reused unchanged, so a verdict difference between the
two engines is a difference in *deciding*, not in plumbing. That is what makes
the S1.7 parity test meaningful.

This module is now only the LangChain binding. Deciding lives elsewhere:

    agentguard/sensors.py   the predicate registry              S2.1
    agentguard/schema.py    the Cedar schema, generated         S2.2
    agentguard/request.py   RuleState -> (Request, Entities)    S2.3
    agentguard/advice.py    the lattice and the join            S2.4
    agentguard/engine.py    load, validate, refuse, decide      S2.5

What is left here is choosing the domain, applying the resolved outcome with
AgentSpec's own enforcement classes, and phrasing the observation the agent sees
exactly as the legacy executor phrases it. S2.6 moves the enforcement mapping to
agentguard/enforcer.py.

One thing is deliberately not general yet: a single hard-coded principal. The
Session entity that carries taints across steps -- the actual thesis
contribution -- is S4.2.

Run the suite through it with:

    AGENTGUARD=cedar .venv/bin/pytest -q tests/test_cedar_executor.py
"""
import agentguard
import profiling
from agent import Action
from controlled_agent_excector import ControlledAgentExecutor
from enforcement import EnforceResult
from agentguard import advice as ag_advice
from agentguard import enforcer as ag_enforcer
from agentguard import engine as ag_engine
from agentguard import request as ag_request
from state import RuleState

# Re-exported so callers and tests have one obvious import per concept while
# the package settles. The definitions live in the modules named above.
PolicyError = ag_engine.PolicyError
PolicyBundle = ag_engine.PolicyBundle
CedarVerdict = ag_engine.Verdict
load_bundle = ag_engine.load
decide = ag_engine.decide


# ---------------------------------------------------------------- sensors
# Selection and evaluation moved to agentguard/request.py (S2.3). The engine no
# longer names sensors at all: it asks for a domain, and the registry's metadata
# decides what can safely run there.

#: Which agent binding this executor guards, unless $AGENTGUARD_DOMAIN says
#: otherwise. Only `code` is wired up; an embodied or shell binding sets its own.
#: Nothing infers it from the action -- see agentguard.domain.
DOMAIN = ag_request.DEFAULT_DOMAIN


def configuration():
    """(policy directory, domain) for this process. Read at construction."""
    return agentguard.policy_dir(), agentguard.domain(default=DOMAIN)


# --------------------------------------------------------------- advice
# The lattice and the join are agentguard/advice.py (S2.4); applying the
# resolved outcome is agentguard/enforcer.py (S2.6). Re-exported here because
# tests and the bench reach for them by the engine's name.

ADVICE_TO_ENFORCEMENT = ag_enforcer.ADVICE_TO_ENFORCEMENT
DEFAULT_ADVICE = ag_advice.DEFAULT
ADVICE_LATTICE = list(ag_advice.LATTICE)
join = ag_advice.join


# --------------------------------------------------------------- executor


class CedarControlledAgentExecutor(ControlledAgentExecutor):
    """ControlledAgentExecutor with the rule loop replaced by a Cedar decision."""

    @classmethod
    def from_agent_and_tools(cls, agent, tools, rules, callbacks=None, **kwargs):
        # Load eagerly: a policy set that does not validate must stop the agent
        # being built, not surface on the first dangerous action.
        load_bundle(*configuration())
        return super().from_agent_and_tools(agent, tools, rules, callbacks, **kwargs)

    def validate_and_enforce(self, action: Action, state: RuleState, _redirects=0):
        """Return (what fired, the action to take) -- same contract as the legacy engine."""
        if action.is_finish():
            # `action finish` is not in the schema until S2.7, and the sensors
            # have no tool input to look at. The legacy engine would still run
            # `trigger finish` rules here; that difference is S2.7's to close.
            return None, action

        profiling.count_rule()
        verdict = decide(load_bundle(*configuration()), state)
        if verdict.allowed:
            return None, action

        with profiling.phase("enforcement"):
            outcome = ag_enforcer.apply(verdict, action, state, tools=self.tools)

        if outcome.redirected:
            # The action changed -- re-planned by llm_self_reflect, or rewritten
            # by a substitution. It has not been through the policy set, and
            # running it unguarded would make @substitute_tool a way around the
            # guard. Bounded, because two policies that redirect to each other
            # would otherwise loop forever.
            if _redirects >= ag_enforcer.MAX_REDIRECTS:
                reason = (f"action stopped by {verdict.raw}\n"
                          f"  note: gave up after {ag_enforcer.MAX_REDIRECTS} redirects")
                return verdict, Action.get_finish(reason, reason)
            if outcome.action.is_finish():
                # llm_self_reflect can re-plan straight to a final answer.
                return verdict, outcome.action
            return self.validate_and_enforce(outcome.action, state, _redirects + 1)

        if outcome.result == EnforceResult.CONTINUE:
            # `user_inspection` where the user approved, or `none`.
            return None, outcome.action
        if outcome.result == EnforceResult.SKIP:
            return verdict, Action.get_skip()
        if outcome.result == EnforceResult.STOP:
            # Phrased exactly as the legacy executor phrases it, so the text the
            # agent and the tests see is identical across engines.
            reason = f"action stopped by {verdict.raw}"
            return verdict, Action.get_finish(reason, reason)
        raise ValueError(f"unreachable enforcement result: {outcome.result}")
