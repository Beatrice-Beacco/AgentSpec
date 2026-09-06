# Latency report

Source: `expres/latency/cedar.jsonl`  ·  36 steps, 23 with at least one rule evaluated

| phase | mean ms | median ms | p95 ms | share of guard |
|---|---:|---:|---:|---:|
| llm_plan | 0.4795 | 0.4045 | 0.8877 |  |
| rule_parse | 0.0000 | 0.0000 | 0.0000 | 0.0% |
| predicate_eval | 0.5104 | 0.2038 | 0.8346 | 49.3% |
| cedar_decide | 0.5067 | 0.4245 | 1.2419 | 48.9% |
| enforcement | 0.0191 | 0.0000 | 0.0697 | 1.8% |
| **guard total** | **1.0362** | 0.6462 | 2.1543 | 100% |

Mean step: 1.6923 ms  ·  guard is 61.2% of it.

> The LLM here is a scripted FakeListLLM, so `llm_plan` is ~0. Against a real model that phase dominates and the guard share collapses -- which is the point: read the guard phases against each other, not against this total.

---

*Regenerated 2026-09-06 at S2.9, together with its counterpart, so the two are
from the same suite on the same machine. The absolute numbers are larger than
the ones S0.11 first recorded (guard total 0.1919 ms) because the suite has
roughly doubled in size since; the **shares** are what carry the argument and
they are unchanged. Compare these two files with each other, never either of
them with a figure from a different run.*
