#!/usr/bin/env python3
"""S1.2 -- can we read an arbitrary @advice annotation from Python?

This blocks the whole enforcement design. Cedar returns Allow/Deny; AgentSpec
has five outcomes (stop, skip, user_inspection, llm_self_reflect,
invoke_action). The plan (thesis §C.4) carries the outcome in an @advice
annotation and reads it off whichever policies determined the decision. If the
annotation is unreachable from Python, that design is dead.

Answer: reachable, but NOT the way the plan assumed.

    diagnostics.id_annotations_by_reason  ->  only @id.  Insufficient.
    policies_to_json_str()                ->  every annotation.  Use this.

Both key on the same synthetic policy ids ("policy0", "policy1", ...) that
diagnostics.reasons returns, so the join is direct and needs no bookkeeping.

    make spike-annotations
"""
import json

from cedarpy import Decision, is_authorized, policies_to_json_str

POLICIES = """
@id("baseline_allow_tools")
permit (principal, action == Action::"invoke", resource);

@id("inspect_system_file_copy")
@advice("user_inspection")
@source("agentspec:pythonrepl.ar#index4")
forbid (principal, action, resource)
when { context.flags.contains("involve_system_file") };

@id("stop_exfiltration")
@advice("stop")
@source("agentspec:pythonrepl.ar#index1")
forbid (principal, action, resource)
when { context.flags.contains("submit_post_request") };
"""

# Most restrictive first. When several policies deny with different advice, the
# outcome is their join -- so it cannot depend on which one Cedar happens to
# list first (and it does not list them in source order; see the demo below).
ADVICE_LATTICE = ["stop", "user_inspection", "llm_self_reflect", "skip", "allow"]


def annotation_table(policies):
    """policy id -> {annotation: value}, built once at load.

    Uses cedarpy's own Cedar-backed parser rather than a regex over the policy
    text, so it cannot drift from what the evaluator actually sees.
    """
    parsed = json.loads(policies_to_json_str(policies))
    return {pid: body.get("annotations", {})
            for pid, body in parsed["staticPolicies"].items()}


def resolve(result, table):
    """Decision + determining policies -> a single enforcement outcome."""
    if result.decision == Decision.Allow:
        return "allow", []
    advice = [(pid, table.get(pid, {}).get("advice", "stop"))
              for pid in result.diagnostics.reasons]
    # Unannotated forbid defaults to "stop": the safe end of the lattice.
    winner = min((a for _, a in advice), key=ADVICE_LATTICE.index)
    return winner, advice


def decide(flags):
    return is_authorized({
        "principal": 'Agent::"a1"',
        "action": 'Action::"invoke"',
        "resource": 'Tool::"python_repl"',
        "context": {"flags": list(flags)},
    }, POLICIES, [])


def main():
    table = annotation_table(POLICIES)

    print("=== what cedarpy exposes ===\n")
    result = decide(["involve_system_file"])
    print(f"  diagnostics.reasons                 : {result.diagnostics.reasons}")
    print(f"  diagnostics.id_annotations_by_reason: {result.diagnostics.id_annotations_by_reason}")
    print("      ^ only @id -- no @advice, no @source. Not enough.\n")
    print("  policies_to_json_str() annotation table:")
    for pid, anns in table.items():
        print(f"      {pid} -> {anns}")

    print("\n=== resolving an outcome ===\n")
    print(f"  {'flags':46s} {'decision':8s} {'advice':16s} contributing")
    print("  " + "-" * 104)

    cases = [
        ([], "allow"),
        (["involve_system_file"], "user_inspection"),
        (["submit_post_request"], "stop"),
        # Both forbids match. stop is more restrictive, so stop wins -- and it
        # must win regardless of the order Cedar lists them in.
        (["involve_system_file", "submit_post_request"], "stop"),
    ]
    ok = True
    for flags, expected in cases:
        result = decide(flags)
        advice, contributing = resolve(result, table)
        detail = ", ".join(f"{table[p].get('id', p)}={a}" for p, a in contributing) or "—"
        print(f"  {str(flags):46s} {str(result.decision).split('.')[1]:8s} "
              f"{advice:16s} {detail}")
        ok &= advice == expected

    print("\n=== order independence ===\n")
    multi = decide(["involve_system_file", "submit_post_request"])
    print(f"  Cedar listed the determining policies as {multi.diagnostics.reasons},")
    print("  which is NOT source order. The lattice join makes that irrelevant;")
    print("  AgentSpec's first-match-wins loop would have returned whichever")
    print("  rule happened to be listed first.")

    print("\nS1.2:", "PASS -- @advice is readable and resolvable" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
