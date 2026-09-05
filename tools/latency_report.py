#!/usr/bin/env python3
"""Summarise the JSONL written by src/profiling.py.

    make profile                     # run the suite with profiling on, then report
    python tools/latency_report.py expres/latency/baseline.jsonl

Reports per-phase mean/median/p95 and, for the guard phases, their share of the
step. Used for plan.md S0.11 (baseline) and again at S2.9 to compare Cedar.
"""
import json
import sys
from statistics import mean, median

PHASES = ["llm_plan", "rule_parse", "predicate_eval", "enforcement"]


def pct(values, q):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def main(path):
    rows = [json.loads(line) for line in open(path) if line.strip()]
    if not rows:
        print(f"{path}: empty")
        return 1

    # A step where no rule triggered says nothing about guard cost; reporting
    # those together with real evaluations would halve every average.
    guarded = [r for r in rows if r.get("rules_evaluated", 0) > 0]

    print(f"# Latency report\n\nSource: `{path}`  ·  {len(rows)} steps, "
          f"{len(guarded)} with at least one rule evaluated\n")
    print("| phase | mean ms | median ms | p95 ms | share of guard |")
    print("|---|---:|---:|---:|---:|")

    guard_total = sum(
        sum(r[f"{p}_ms"] for p in PHASES if p != "llm_plan") for r in guarded
    )
    for phase in PHASES:
        values = [r[f"{phase}_ms"] for r in (guarded if phase != "llm_plan" else rows)]
        share = ""
        if phase != "llm_plan" and guard_total:
            share = f"{100 * sum(values) / guard_total:.1f}%"
        print(f"| {phase} | {mean(values):.4f} | {median(values):.4f} | "
              f"{pct(values, 0.95):.4f} | {share} |")

    guard = [r["guard_ms"] for r in guarded]
    total = [r["total_ms"] for r in guarded]
    print(f"| **guard total** | **{mean(guard):.4f}** | {median(guard):.4f} | "
          f"{pct(guard, 0.95):.4f} | 100% |")
    print(f"\nMean step: {mean(total):.4f} ms  ·  guard is "
          f"{100 * sum(guard) / sum(total):.1f}% of it.")
    print("\n> The LLM here is a scripted FakeListLLM, so `llm_plan` is ~0. Against a "
          "real model that phase dominates and the guard share collapses -- which is "
          "the point: read the guard phases against each other, not against this total.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "expres/latency/baseline.jsonl"))
