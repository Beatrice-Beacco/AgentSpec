#!/usr/bin/env python3
"""S1.4 -- how long does one Cedar decision take?

The number this produces goes straight against the S0.11 baseline, where 78% of
AgentSpec's guard cost turned out to be re-lexing and re-parsing rule text on
every single action (docs/baseline-latency.md).

Two configurations are measured, because the difference between them is the
architectural point:

    policy text   is_authorized(request, POLICY_STRING, ...) -- Cedar reparses
                  the text on every call, which is what AgentSpec does
    PolicySet     parsed once up front, then reused -- what an engine should do

    make spike-latency
"""
import statistics
import time

from cedarpy import PolicySet, Schema, is_authorized

N = 10_000

SCHEMA = """
entity Agent = { framework: String };
entity Tool  = { kind: String, reversible: Bool };
action invoke appliesTo {
  principal: [Agent],
  resource: [Tool],
  context: { flags: Set<String>, risk: Long }
};
"""

POLICIES = """
@id("baseline")
permit (principal, action == Action::"invoke", resource);

@id("no_destructive")
@advice("stop")
forbid (principal, action == Action::"invoke", resource)
when { context.flags.contains("destuctive_os_inst") };

@id("inspect_system_file")
@advice("user_inspection")
forbid (principal, action == Action::"invoke", resource)
when { context.flags.contains("involve_system_file") && context.risk > 20 };
"""

REQUEST = {
    "principal": 'Agent::"a1"',
    "action": 'Action::"invoke"',
    "resource": 'Tool::"python_repl"',
    "context": {"flags": ["destuctive_os_inst"], "risk": 40},
}
ENTITIES = [
    {"uid": {"type": "Agent", "id": "a1"}, "attrs": {"framework": "langchain"}, "parents": []},
    {"uid": {"type": "Tool", "id": "python_repl"},
     "attrs": {"kind": "code_exec", "reversible": False}, "parents": []},
]


def measure(label, policies, entities, schema=None, n=N):
    samples = []
    for _ in range(n):
        start = time.perf_counter()
        result = is_authorized(REQUEST, policies, entities, schema)
        samples.append((time.perf_counter() - start) * 1000)
    assert not result.diagnostics.errors, result.diagnostics.errors

    ordered = sorted(samples)
    return {
        "label": label,
        "mean": statistics.mean(samples),
        "median": statistics.median(samples),
        "p95": ordered[int(0.95 * (n - 1))],
        "p99": ordered[int(0.99 * (n - 1))],
        "max": ordered[-1],
    }


def main():
    parsed_policies = PolicySet.from_str(POLICIES)
    parsed_schema = Schema.from_str(SCHEMA)

    runs = [
        measure("policy text, no schema", POLICIES, ENTITIES),
        measure("policy text + schema", POLICIES, ENTITIES, parsed_schema),
        measure("PolicySet parsed once", parsed_policies, ENTITIES, parsed_schema),
    ]

    print(f"{N:,} authorizations, 3 policies, 2 entities\n")
    print(f"{'configuration':26s} {'mean ms':>9s} {'median':>9s} {'p95':>9s} "
          f"{'p99':>9s} {'max':>9s}")
    print("-" * 78)
    for r in runs:
        print(f"{r['label']:26s} {r['mean']:9.4f} {r['median']:9.4f} "
              f"{r['p95']:9.4f} {r['p99']:9.4f} {r['max']:9.4f}")

    reparse, reused = runs[1]["mean"], runs[2]["mean"]
    # From docs/baseline-latency.md (S0.11), mean ms per agent step.
    agentspec_parse, agentspec_guard = 0.1512, 0.1919

    print(f"""
Against the S0.11 baseline (docs/baseline-latency.md):

  AgentSpec rule_parse, per step        {agentspec_parse:7.4f} ms   (78.8% of its guard cost)
  AgentSpec guard total, per step       {agentspec_guard:7.4f} ms
  Cedar, reparsing policy text          {reparse:7.4f} ms
  Cedar, PolicySet parsed once          {reused:7.4f} ms   {reparse / reused:.1f}x faster than reparsing

A whole Cedar decision costs less than AgentSpec spends on parsing alone
({reused:.4f} vs {agentspec_parse:.4f} ms), and {agentspec_guard / reused:.1f}x less than its full guard path --
while doing strictly more work: three policies instead of one rule, schema
validation, and an order-independent result.

Read the ratio, not the absolutes. Both are microseconds against an LLM call
measured in hundreds of milliseconds, so neither is a latency problem. The point
is that the avoidable work AgentSpec pays on every action is avoidable *by
default* in Cedar -- a PolicySet is parsed once because that is the natural way
to use the API, not because someone remembered to optimise.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
