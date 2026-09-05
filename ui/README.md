# The test bench

A local web UI for exercising AgentSpec rules. Start it:

```bash
make ui
```

Then open <http://127.0.0.1:5000>. The **Help** tab in the app is the user guide —
this file is the implementation note.

## Why it exists

`plan.md` **S0.13**. After every step we need to answer "does the rule engine still
behave?" without an API key, without a benchmark dataset, and without reading a
traceback. The bench takes rules + one proposed action and reports the verdict plus
*why* each rule did or didn't fire.

It runs the real `ControlledAgentExecutor`, driven by a `FakeListLLM` scripted from
the action you type. Same code path as production, deterministic input. The tool is
a stub that records and returns `"OK"` — nothing you type is ever executed.

## Layout

| File | Does |
|---|---|
| `engine.py` | parse-checking, per-rule diagnostics, running the executor |
| `app.py` | Flask routes and the rule-library path guard |
| `examples.py` | the 8 worked examples, pinned by `tests/test_ui_examples.py` |
| `templates/index.html` | the bench |
| `templates/help.html` | the user guide |
| `static/` | one stylesheet, one script, no build step |
| `rules/` | your scratch rules — safe to edit, not part of the corpus |

## API

Everything the page does is a plain JSON endpoint, so the bench is scriptable:

| Route | Body | Returns |
|---|---|---|
| `GET /api/state` | — | rule library, examples, predicate names, active engine |
| `POST /api/parse` | `{text}` | per-rule id, clauses, syntax errors |
| `POST /api/probe` | `{user_input, tool_input, intermediate_steps}` | every predicate's value |
| `POST /api/run` | `+ {rule_text, tool_name, approve}` | verdict, explain, steps, trace, cedar |
| `GET/POST /api/rule` | `{path, text}` | read / write a rule file |

`/api/run` already returns a `cedar` key (`{"status": "not_implemented"}`) so the
page needs no restructuring when S1.7 lands.

## Notes for later steps

- **S1.8** fills the Cedar panel; **S2.10** adds the engine toggle and a compare
  mode; **S4.8** adds the session/taint viewer. The response shape anticipates all
  three.
- Writes are confined to `ui/rules/` and `src/rules/` by `app._safe`, asserted in
  `tests/test_ui_examples.py`. The bench binds `127.0.0.1` only: it evaluates
  arbitrary predicates and edits files, so it must never face a network.
- `engine.py` duplicates a little of `tests/conftest.py`. Left deliberate for now —
  the tests should not depend on the UI. Worth unifying if a third caller appears.
