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
import profiling
from agent import Action
from controlled_agent_excector import ControlledAgentExecutor
from enforcement import ENFORCEMENT_TO_CLASS, EnforceResult
from agentguard import advice as ag_advice
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

#: Which agent binding this executor guards. Only `code` is wired up; an
#: embodied or shell binding sets its own. Nothing infers it from the action.
DOMAIN = ag_request.DEFAULT_DOMAIN


# ---------------------------------------------------------------- advice
# The lattice, the join and the substitution rule live in agentguard/advice.py
# (S2.4). What stays here is the map onto AgentSpec's own enforcement classes,
# which S2.6 moves to agentguard/enforcer.py.

#: Advice -> the key in AgentSpec's ENFORCEMENT_TO_CLASS. The lattice names were
#: chosen to line up with it, so this is almost an identity; the one real entry
#: is `allow`, which AgentSpec spells `none`. `substitute` has no entry: the
#: baseline's InvokeAction is unregistered and a no-op (docs/findings.md D-5),
#: so S2.6 has to implement the rewrite rather than delegate it.
ADVICE_TO_ENFORCEMENT = {
    ag_advice.ALLOW: "none",
    ag_advice.SKIP: "skip",
    ag_advice.LLM_SELF_REFLECT: "llm_self_reflect",
    ag_advice.USER_INSPECTION: "user_inspection",
    ag_advice.STOP: "stop",
}

#: Re-exported so callers do not reach past the engine for the common cases.
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
        load_bundle(domain=DOMAIN)
        return super().from_agent_and_tools(agent, tools, rules, callbacks, **kwargs)

    def validate_and_enforce(self, action: Action, state: RuleState):
        """Return (what fired, the action to take) -- same contract as the legacy engine."""
        if action.is_finish():
            # `action finish` is not in the schema until S2.7, and the sensors
            # have no tool input to look at. The legacy engine would still run
            # `trigger finish` rules here; that difference is S2.7's to close.
            return None, action

        profiling.count_rule()
        verdict = decide(load_bundle(domain=DOMAIN), state)
        if verdict.allowed:
            return None, action

        enforcement = ENFORCEMENT_TO_CLASS[ADVICE_TO_ENFORCEMENT[verdict.advice]]
        with profiling.phase("enforcement"):
            outcome, next_action = enforcement(state=state).apply(action)

        if outcome == EnforceResult.CONTINUE:
            # `user_inspection` where the user approved, or `none`.
            return None, action
        if outcome == EnforceResult.SKIP:
            return verdict, Action.get_skip()
        if outcome == EnforceResult.STOP:
            # Phrased exactly as the legacy executor phrases it, so the text the
            # agent and the tests see is identical across engines.
            reason = f"action stopped by {verdict.raw}"
            return verdict, Action.get_finish(reason, reason)
        if outcome == EnforceResult.SELF_REFLECT:
            return self.validate_and_enforce(next_action, state)
        raise ValueError(f"unreachable enforcement result: {outcome}")
