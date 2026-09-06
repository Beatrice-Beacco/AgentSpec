# Cedar spikes — findings

Answers to the unknowns Sprint 1 exists to resolve, before any engine code is
written. Each spike is runnable: `make spike-hello`, `make spike-annotations`.

Environment: `cedarpy` 4.8.7 (wrapping Cedar 4.8.x), Python 3.12.8.

---

## S1.1 — does a Cedar decision work at all? ✅

`spikes/hello_cedar.py`. Two requests against one policy set, in the PARC shape
the thesis proposes rather than the Cedar docs' photo-album example:

| proposed action | flags | decision | determining policy |
|---|---|---|---|
| `print(6 * 7)` | `[]` | **Allow** | `baseline_allow_tools` |
| `os.remove("notes.txt")` | `["destuctive_os_inst"]` | **Deny** | `no_destructive_os_call` |

The shape that matters:

```
principal  Agent::"a1"          the agent
action     Action::"invoke"     invoking a tool
resource   Tool::"python_repl"  the tool
context    {"flags": [...]}     what the Python predicates found
```

`flags` is the whole architectural idea. Cedar expressions are pure and total —
no regex, no AST walking, no I/O — so `destuctive_os_inst` can never run *inside*
a policy. It runs first, in Python, and arrives as a context attribute. Detection
stays in Python; the decision moves to Cedar. That split is M1 in the thesis plan.

---

## S1.2 — can we read an arbitrary `@advice` annotation? ✅ (not as assumed)

**This blocked the enforcement design.** Cedar returns Allow/Deny; AgentSpec has
five outcomes. The plan carries the outcome in an `@advice` annotation and reads
it off whichever policies determined the decision. If that were unreachable from
Python, the design was dead.

### The plan's first choice does not work

`diagnostics.id_annotations_by_reason` returns **only `@id`**:

```python
diagnostics.reasons                  -> ['policy1']
diagnostics.id_annotations_by_reason -> {'policy1': 'inspect_system_file_copy'}
```

No `@advice`, no `@source`. The name is accurate and the plan misread it — it is
"the `@id` annotation, by reason", not "annotations, by reason".

### `policies_to_json_str()` does work

```python
json.loads(policies_to_json_str(POLICIES))["staticPolicies"]

  policy1 -> {'advice': 'user_inspection',
              'id': 'inspect_system_file_copy',
              'source': 'agentspec:pythonrepl.ar#index4'}
```

Every annotation, keyed by the **same** synthetic ids (`policy0`, `policy1`, …)
that `diagnostics.reasons` returns. So the join is direct and needs no
bookkeeping of our own.

> **Decision:** build the annotation side-table once at policy-set load with
> `policies_to_json_str()`, and join it to `diagnostics.reasons` at decision
> time. This is cedarpy's own Cedar-backed parser, not a regex over policy text,
> so the table cannot drift from what the evaluator sees. The fallbacks the plan
> listed — hand-parsing annotations, the Cedar CLI's JSON, a bespoke PyO3
> wrapper — are all unnecessary.

### The advice lattice is not hypothetical

Two `forbid` policies can both determine one decision:

| flags | decision | advice | contributing |
|---|---|---|---|
| `[]` | Allow | `allow` | — |
| `[involve_system_file]` | Deny | `user_inspection` | `inspect_system_file_copy` |
| `[submit_post_request]` | Deny | `stop` | `stop_exfiltration` |
| both | Deny | **`stop`** | `stop_exfiltration=stop`, `inspect_system_file_copy=user_inspection` |

The join takes the most restrictive: `stop > user_inspection > llm_self_reflect
> skip > allow`. An unannotated `forbid` defaults to `stop`, the safe end.

**And the order matters more than expected.** For the two-flag case Cedar
returned `['policy2', 'policy1']` — *not* source order. Any scheme that took
"the first determining policy" would be reading an unspecified ordering.
AgentSpec's `validate_and_enforce` does exactly that with its rule list, which
is why `skip` before `stop` gives SKIPPED and the reverse gives STOPPED
(see `ui/examples.py` example 8). The lattice join makes ordering irrelevant by
construction — this is the concrete mechanism behind thesis claim M2, and it
gives S2.8 its property to test.

---

## S1.3 — what does validation catch before anything runs? ✅

`spikes/validation.py`. Eight policies against a schema:

| case | result |
|---|---|
| valid policy | passes |
| typo in context attribute (`context.rsik`) | **caught** — ``attribute `rsik` in context for Action::"invoke" not found`` |
| typo in entity attribute (`resource.kindd`) | **caught** |
| type mismatch (`context.risk == "high"`) | **caught** — `the types Long and String are not compatible` |
| unknown entity type (`Widget::"w"`) | **caught** |
| unknown action (`Action::"delet"`) | **caught** |
| misspelled flag, `Set<String>` schema | **MISSED** |
| misspelled flag, record-of-`Bool` schema | **caught** |

Five of six malformed policies are rejected before a single agent step runs.
AgentSpec catches none of these — there is no schema to check a rule against, and
`tests/test_fail_open.py` documents the four ways a bad rule gets through instead.

### This settles S2.2 early

The last two rows are the *same typo* under two schema designs:

- **`flags: Set<String>`** — any string is a valid set member, so
  `context.flags.contains("involve_system_fyle")` type-checks. The result is a
  safety policy that silently never fires: exactly the failure mode we are
  leaving behind.
- **`flags: { involve_system_file: Bool, … }`** — the attribute does not exist,
  and validation fails with the misspelled name.

> **Decision:** S2.2 generates a record-of-`Bool` schema from the predicate
> registry and accepts the codegen step. The plan recommended this on principle;
> this is the evidence.

**Done in S2.2**, with one refinement this spike did not anticipate: the Bools are
**optional** (`name?: Bool`), not required. Required attributes force the request
to carry all 36 flags or Cedar answers `NoDecision` — which would mean sending
`false` for the 35 sensors that never ran, asserting "not happening" about checks
nobody performed. Optional attributes let the request carry exactly what was
evaluated, and Cedar then *refuses to validate* an unguarded access
(`unable to guarantee safety of access`), so a policy must write
`context.flags has X && context.flags.X` and cannot conflate the two. The
verbosity is the honesty. See `tests/test_schema_codegen.py`.

---

## S1.4 — how fast is a decision? ✅

`spikes/latency.py`. 10,000 authorizations, 3 policies, 2 entities:

| configuration | mean ms | median | p95 | p99 |
|---|---:|---:|---:|---:|
| policy text, no schema | 0.1124 | 0.1082 | 0.1272 | 0.2087 |
| policy text + schema | 0.1196 | 0.1157 | 0.1297 | 0.1844 |
| **`PolicySet` parsed once** | **0.0579** | 0.0577 | 0.0645 | 0.0772 |

Against the S0.11 baseline (`docs/baseline-latency.md`):

| | mean ms per step |
|---|---:|
| AgentSpec `rule_parse` alone | 0.1512 |
| AgentSpec guard total | 0.1919 |
| Cedar, `PolicySet` parsed once | **0.0579** |

**A whole Cedar decision costs less than AgentSpec spends on parsing alone**, and
3.3× less than its full guard path — while doing strictly more work: three
policies rather than one rule, schema validation, and an order-independent result.

Read the ratio, not the absolutes. Both are microseconds against an LLM call
measured in hundreds of milliseconds, so neither is a latency problem, and the
honest RQ5 finding remains "the policy engine is free; detection is the cost."
The point is narrower: the avoidable work AgentSpec pays on every action is
avoidable *by default* in Cedar. A `PolicySet` is parsed once because that is the
natural way to use the API — not because someone remembered to optimise.

Passing policy text rather than a `PolicySet` costs 2× and is the trap to avoid
in `agentguard/engine.py`.

---

## Still open

| Question | Step | Answer |
|---|---|---|
| Does the record-of-`Bool` schema stay maintainable as predicates are added? | S2.2 | **Yes** — `agentguard/schema.py` generates it from the sensor registry, `make schema` regenerates, and `make validate` fails if the file on disk has drifted. Adding a predicate needs no schema edit. |
| Does partial evaluation let us filter tools before the agent sees them? | later | open |
