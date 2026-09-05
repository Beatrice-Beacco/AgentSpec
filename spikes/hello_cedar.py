#!/usr/bin/env python3
"""S1.1 -- the smallest Cedar decision, in AgentSpec's shape.

Not the Cedar docs' photo-album example: this uses the PARC mapping the thesis
actually proposes (plan.md §C.1), so the request shape here is the one
agentguard/request.py will build for real.

    principal  the agent           Agent::"a1"
    action     invoking a tool     Action::"invoke"
    resource   the tool itself     Tool::"python_repl"
    context    materialised flags  {"flags": [...]}

The flags are the key idea. Cedar expressions are pure and total -- no regex, no
AST walking -- so `destuctive_os_inst` cannot run *inside* a policy. It runs
first, in Python, and its result arrives as a context attribute. Detection stays
in Python; the decision moves to Cedar.

    make spike-hello
"""
from cedarpy import Decision, is_authorized

# Default-deny: without a matching permit, nothing is allowed. The forbid then
# carves an exception out of the baseline. Order is irrelevant -- forbid always
# wins -- which is the property AgentSpec's first-match-wins loop lacks.
POLICIES = """
@id("baseline_allow_tools")
permit (
  principal,
  action == Action::"invoke",
  resource
);

@id("no_destructive_os_call")
@advice("stop")
@source("agentspec:src/rules/manual/pythonrepl.ar")
forbid (
  principal,
  action == Action::"invoke",
  resource == Tool::"python_repl"
)
when { context.flags.contains("destuctive_os_inst") };
"""


def decide(flags):
    """One authorization call. `flags` is what the Python predicates found."""
    request = {
        "principal": 'Agent::"a1"',
        "action": 'Action::"invoke"',
        "resource": 'Tool::"python_repl"',
        "context": {"flags": list(flags)},
    }
    return is_authorized(request, POLICIES, [])


def main():
    cases = [
        ("print(6 * 7)", [], Decision.Allow),
        ('os.remove("notes.txt")', ["destuctive_os_inst"], Decision.Deny),
    ]

    print(f"{'proposed action':28s} {'flags':26s} {'decision':10s} determining policy")
    print("-" * 92)
    ok = True
    for action, flags, expected in cases:
        result = decide(flags)
        reasons = ", ".join(result.diagnostics.reasons) or "—"
        named = ", ".join(result.diagnostics.id_annotations_by_reason.values()) or "—"
        print(f"{action:28s} {str(flags):26s} {str(result.decision):18s} "
              f"{reasons} ({named})")
        ok &= result.decision == expected
        assert not result.diagnostics.errors, result.diagnostics.errors

    print("\nS1.1:", "PASS -- Allow and Deny both reached" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
