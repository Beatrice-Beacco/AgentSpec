# Legacy rule examples — a language the grammar never implemented

These three files shipped with AgentSpec as `spec_lang/rule_examples/*.ar`, and
its own unit test (`spec_lang/test_parse.py`) parses them. **All three fail.**
They are kept here, unmodified, because *why* they fail is a finding — see
`docs/findings.md` D-10 — and the working fixtures in the directory above
replace them for the purpose the test actually serves.

They use four constructs the shipped grammar has no rule for:

| construct | example | grammar |
|---|---|---|
| `act` before the event | `trigger act TerminalExecute` | `event` is a bare identifier; `act` is consumed as the event and the real name is extraneous |
| a `prepare` clause | `prepare val light_states = invoke_action(...)` | `rule` is `ruleClause triggerClause checkClause enforceClause END` — there is no fifth clause |
| string arguments to a predicate | `llm_judge(cur_action["command"], "Return true if ...")` | `predicate_func: IDENTIFIER LPAREN number RPAREN` — one argument, and it must be a number |
| subscripting | `light["light_states"]["traffic_id"]` | `value` supports it, but `predicate` cannot reach `value` |

The direction matters: these are not typos, they are a **more expressive**
language than the one that was implemented. `prepare` binds the result of a tool
call for later checks; `llm_judge` passes a natural-language question to a model.
Both are real ideas, and neither survives into the grammar or the runtime.

Preserved so the divergence stays visible in the tree rather than only in
`git log`.
