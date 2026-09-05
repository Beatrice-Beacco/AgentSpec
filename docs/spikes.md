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

## Still open

| Question | Step |
|---|---|
| Does `validate_policies()` catch a typo'd attribute against a schema? | S1.3 |
| What is the per-decision latency at 10k calls? | S1.4 |
| Record-of-bools vs `Set<String>` for flags — which does the validator catch more with? | S2.2 |
