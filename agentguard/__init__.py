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

POLICY_DIR = os.path.join(REPO_ROOT, "policies")

#: Value of $AGENTGUARD that selects this engine.
CEDAR = "cedar"


def enabled(environ=None):
    """Is the Cedar engine selected? Read at agent construction, not import."""
    environ = os.environ if environ is None else environ
    return environ.get("AGENTGUARD", "legacy").strip().lower() == CEDAR
