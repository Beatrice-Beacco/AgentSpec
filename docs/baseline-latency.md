# Latency report

Source: `expres/latency/baseline.jsonl`  ·  31 steps, 17 with at least one rule evaluated

| phase | mean ms | median ms | p95 ms | share of guard |
|---|---:|---:|---:|---:|
| llm_plan | 0.1322 | 0.1121 | 0.2032 |  |
| rule_parse | 0.1512 | 0.1197 | 0.2120 | 78.8% |
| predicate_eval | 0.0334 | 0.0151 | 0.1144 | 17.4% |
| enforcement | 0.0074 | 0.0048 | 0.0176 | 3.8% |
| **guard total** | **0.1919** | 0.1485 | 0.2573 | 100% |

Mean step: 0.3673 ms  ·  guard is 52.2% of it.

> The LLM here is a scripted FakeListLLM, so `llm_plan` is ~0. Against a real model that phase dominates and the guard share collapses -- which is the point: read the guard phases against each other, not against this total.
