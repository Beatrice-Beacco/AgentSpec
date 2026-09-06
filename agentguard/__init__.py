"""AgentGuard -- the Cedar policy engine behind AgentSpec's guard decisions.

Selected at runtime with `AGENTGUARD=cedar`; anything else keeps the original
engine. Both are meant to stay runnable side by side for the whole project, so
every result can be reported as a comparison rather than an assertion.

The package deliberately starts as one module. The seams where plan.md's
Sprint 2 splits it apart are marked in `executor.py`, so the split is a move
rather than a rewrite:

    sensors.py   S2.1   the predicate registry
    schema.py    S2.2   schema generated from that registry
    request.py   S2.3   RuleState -> (Request, Entities)
    advice.py    S2.4   the advice lattice
    engine.py    S2.5   policy loading, validation, decision
    enforcer.py  S2.6   advice -> enforcement.py

`src/` is not a package -- its modules import each other flatly (`from rule
import Rule`) -- so it has to be on sys.path before anything here can import
them. tests/conftest.py does the same thing for the same reason.
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

#: Where the policy set lives by default.
POLICY_DIR = os.path.join(REPO_ROOT, "policies")

#: Value of $AGENTGUARD that selects this engine.
CEDAR = "cedar"

#: Point the engine at a different policy directory. A deployment property, not
#: a per-call one -- see `policy_dir` for why that distinction matters.
POLICY_DIR_VAR = "AGENTGUARD_POLICIES"

#: Which sensor domain the guarded agent belongs to (code / embodied / ...).
DOMAIN_VAR = "AGENTGUARD_DOMAIN"


def enabled(environ=None):
    """Is the Cedar engine selected? Read at agent construction, not import."""
    environ = os.environ if environ is None else environ
    return environ.get("AGENTGUARD", "legacy").strip().lower() == CEDAR


def policy_dir(environ=None):
    """Where to load policies from.

    **Policy is ambient here, and that is a deliberate difference from
    AgentSpec.** AgentSpec takes its rules as a constructor argument, so a
    caller who can build the executor can build it with no rules and get no
    guard -- the guard is opt-in per construction site. AgentGuard reads its
    policy set from the environment instead, so it is deployment configuration:
    the code being guarded cannot choose to be unguarded.

    The cost is that "run with these rules" has no direct equivalent, which is
    why `tests/test_enforcement.py::test_no_rules_means_no_interference` needs a
    Cedar-side translation rather than passing `rules=[]`. The env var is what
    makes that translation possible without a per-call argument.
    """
    environ = os.environ if environ is None else environ
    return environ.get(POLICY_DIR_VAR, "").strip() or POLICY_DIR


def domain(environ=None, default=None):
    """Which sensor domain the guarded agent belongs to.

    Not inferred from the action: an embodied agent that happens to call a tool
    named like a code tool is still an embodied agent, and guessing would run
    sensors that raise on the wrong trace shape (S2.1).
    """
    environ = os.environ if environ is None else environ
    return environ.get(DOMAIN_VAR, "").strip() or default
