# Rule examples — fixtures for `spec_lang/test_parse.py`

Four rules that between them exercise every construct the **shipped** grammar
implements. They are parser fixtures, not policy: their job is to fail loudly if
`AgentSpec.g4` regresses.

| file | covers |
|---|---|
| `predicate.ar` | the minimal well-formed rule: trigger, one registered predicate, one enforcement |
| `inspect_dangerous_command_before_execution.ar` | several checks (implicit AND) and a negation `!p` |
| `conflict_light_status.ar` | `state_change` trigger, a parameterised predicate, and `config` enforcement — the apollo shape |
| `invoke_action.ar` | the substitution enforcement. It *parses*; it does not execute, because `InvokeAction` is never registered (`docs/findings.md` D-5) |

**None of them carries a comment**, and that is not an oversight: the shipped
grammar has no comment token, so a single `//` line makes the whole file
unparseable. That is why this explanation is in Markdown beside the fixtures
rather than in them.

`legacy/` holds the three originals, unmodified. All three fail to parse; see
that directory's README and `docs/findings.md` D-10.
