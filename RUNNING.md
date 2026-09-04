# Running & testing AgentSpec

Notes from an actual from-scratch setup of this fork on macOS / Python 3.12.
Everything below was executed, not guessed.

---

## 1. What state the repo is in

Two things to know before you start:

- **The benchmark datasets are not in the repo.** `benchmarks/RedCode/` and
  `benchmarks/SafeAgentBench/` are **empty directories**. Only
  `benchmarks/ToolEmu/` has data (`all_cases.json`, `all_toolkits.json`).
  So `src/code_agent.py` and `src/embodied_agent.py` **cannot run as-is** — they
  open files that don't exist.
- **There is no working test suite.** The one unit test in the repo fails, and
  `src/interpreter.py`'s built-in `test_interpret()` crashes. Details in §5.

So "run the paper's experiments" is a multi-day task (fetch datasets, get an
OpenAI key, budget for API calls). "Verify the enforcement mechanism works" is a
two-minute task — that's §4, and it's what you want first.

---

## 2. Setup

```bash
cd AgentSpec
python3 -m venv .venv
```

Do **not** use `pip install -r requirement.txt` unchanged. It pins nothing, and
it pulls `ai2thor` (a Unity simulator, ~hundreds of MB, needs a display) which
you only need for the embodied experiments. Install the pinned set instead:

```bash
.venv/bin/pip install "antlr4-python3-runtime==4.13" "langchain==0.3.25" "langchain-openai" "langchain-community<0.3.27" "langchain-experimental<0.4"
```

This resolves to a working environment:

| package | version |
|---|---|
| langchain | 0.3.25 |
| langchain-core | 0.3.86 |
| langchain-community | 0.3.25 |
| langchain-experimental | 0.3.4 |
| langchain-openai | 0.3.35 |
| antlr4-python3-runtime | 4.13.0 |

> The README's "working version" list is inconsistent — it mixes LangChain 0.3.x
> with `langchain-classic` 1.0.1, which belong to different major lines. The code
> imports `langchain.agents.loading.AGENT_TO_CLASS` and
> `langchain._api.deprecation.AGENT_DEPRECATION_WARNING`, which exist in **0.3.x**.
> Stay on 0.3.x. On LangChain 1.x those moved to `langchain_classic`.

Verify the imports:

```bash
cd src && ../.venv/bin/python -c "import interpreter, controlled_agent_excector, rule, state; print('OK')"
```

`SyntaxWarning: invalid escape sequence '\.'` from `rules/manual/pythonrepl.py`
is harmless (unescaped regex in a normal string).

### Two things that will bite you

1. **The imports are flat.** `src/*.py` does `from rule import Rule`, not
   `from src.rule import Rule`. You must either run from inside `src/`, or put
   `src/` on `PYTHONPATH`, or `sys.path.insert(0, "src")`.
2. **Relative data paths.** `code_agent.py` opens `benchmarks/...` relative to
   the **current working directory**, but must be imported from `src/`. Those two
   requirements contradict each other; you'll need to fix the paths.

### Optional

- **OpenAI key** (only for real agent runs): `export OPENAI_API_KEY=sk-...`
- **Java** (only if you edit the grammar): the generated parser is committed, so
  you don't need Java unless you change `src/spec_lang/AgentSpec.g4`. If you do:
  ```bash
  cd src && bash run.sh   # runs gen.py, then ANTLR over the .g4
  ```
- **`ai2thor`** (only for embodied experiments): needs a display; use Xvfb headless.

---

## 3. The mental model

Everything happens in one method: `ControlledAgentExecutor._iter_next_step`
in `src/controlled_agent_excector.py`. It overrides LangChain's agent loop so
that between "the LLM decided on an action" and "the tool actually runs", the
rules get a veto:

```
LLM plans ──▶ Action.from_langchain(output)
          ──▶ RuleState(action, agent, intermediate_steps, user_input)
          ──▶ validate_and_enforce(action, state)
                 for rule in self.rules:
                     if rule.triggered(action.name, action.input):
                         RuleInterpreter(rule, state).verify_and_enforce(action)
                         → CONTINUE | SKIP | STOP | SELF_REFLECT
          ──▶ tool executes (or doesn't)
```

Read that method first. Nothing else in the repo matters as much.

---

## 4. The fast path: verify enforcement works (no API key)

```bash
.venv/bin/python smoke_test.py
```

`smoke_test.py` scripts a `FakeListLLM` so the agent deterministically proposes a
known action, then checks the rule engine's response:

- **Scenario A** — agent proposes `os.remove("notes.txt")`; the rule must **stop**
  it, and the tool must never run.
- **Scenario B** — agent proposes `print(6 * 7)`; no rule fires, the tool runs,
  output is `42`. (This is your false-positive check — a guard that blocks
  everything would "pass" Scenario A alone.)

Expected output ends with `SMOKE TEST: PASS`.

This is the loop you'll be replacing with Cedar, so make sure you can run it,
break it deliberately, and watch it fail.

### Writing your own rule

```
rule @block_file_deletion
trigger
    python_repl            ← must equal the tool's `.name` EXACTLY
check
    destuctive_os_inst     ← must be in BOTH the grammar and the predicate table
enforce
    stop
end
```

Three constraints that are easy to get wrong:

- **`trigger`** is matched by `Rule.triggered()` as: `event == "any"` **or**
  `tool_name == event` **or** `str(tool_input).startswith(event.replace("_", " "))`.
  That last clause is why embodied rules use triggers like `turn_on` — it becomes
  the prefix `"turn on"` matched against the tool input string.
- **`check`** predicates must appear in **both** places or the rule silently
  breaks: the `PREDICATE` token in `src/spec_lang/AgentSpec.g4` *and*
  `rules.manual.table.predicate_table`. Adding a predicate means editing the
  grammar and re-running ANTLR. (They're currently in sync: 36 each.)
- **`enforce`** — use `stop` or `skip` for anything automated.
  **`user_inspection` calls `input()`** and will hang a non-interactive run.
  Note the grammar accepts `llm_self_reflect`; the README's `llm_self_examine`
  does **not** parse.

To confirm your rule text is valid before wiring it in:

```bash
cd src && ../.venv/bin/python -c "
from rule import Rule
print(Rule.from_text(open('../my_rule.ar').read()))"
```

⚠️ **`Rule.from_text` does not raise on a parse error.** It prints to the console
and returns a Rule anyway. Watch stderr — silence means success.

---

## 5. Auditing the rule corpus

```bash
.venv/bin/python tools/audit_rules.py src
```

Parses every shipped `.ar`/`.rule` file with the repo's own generated parser and
emits Markdown tables. Current results:

| File | Rules | Parse OK | Parse FAIL |
|---|---:|---:|---:|
| `src/rules/manual/pythonrepl.ar` | 26 | 10 | **16** |
| `src/rules/manual/toolemu.ar` | 11 | 0 | **11** |
| `src/rules/manual/embodied.ar` | 5 | 2 | **3** |

Causes: no `//` comment token in the grammar; `&` and `|` used in rule files but
absent from the grammar; dotted (`Gmail.SendMail`) and multi-word (`turn on`)
triggers rejected; `True` capitalised; predicates not in the closed token list.

**The repo's own tests do not pass:**

```bash
PYTHONPATH=src .venv/bin/python -m unittest spec_lang.test_parse -v
# FAILED — fixtures in src/spec_lang/rule_examples/ use an older language
# version (`trigger act X`, a `prepare` clause, `eq(...)`, `llm_judge(...)`)
# that the current grammar rejects.

cd src && ../.venv/bin/python interpreter.py
# ValueError: Syntax error at line 3, column 11: mismatched input '.' expecting 'check'
# — its own test rule uses the dotted trigger `Todoist.TodoistDeleteTask`.
```

`src/translator.py` (AgentSpec → uDrive, for the AV domain) **does** run:
`cd src && ../.venv/bin/python translator.py`.

---

## 6. Local fix applied

`src/rule.py` — `Rule.triggered()` is patched. The original:

```python
return self.event == "any" or action_name == self.event \
       or input.strip().startswith(self.event.replace("_",' '))
```

`input` is `None` for `AgentFinish` actions (see `Action.get_finish`), and a
`dict` for structured tool inputs. Because of Python's `and`/`or` precedence in
`validate_and_enforce`, this line is reached on **every** finish action, so
**any normal task completion crashed with `AttributeError` whenever a
tool-triggered rule was loaded.** Scenario B of the smoke test reproduces it on
the unpatched code.

Minimal reproduction:

```python
# from src/, on the UNPATCHED rule.py
from rule import Rule
from agent import Action
from langchain_core.agents import AgentFinish

rule_text = "rule @x\ntrigger\n python_repl\ncheck\n destuctive_os_inst\nenforce\n stop\nend\n"
r = Rule.from_text(rule_text)
a = Action.from_langchain(AgentFinish({"output": "42"}, "log"))
print(a.name, a.input)      # -> finish None
r.triggered(a.name, a.input)  # AttributeError: 'NoneType' object has no attribute 'strip'
```

The fix guards `None` and coerces non-strings. It is **uncommitted** — review it
before committing, and consider reporting it upstream.

---

## 7. Running the real experiments (the slow path)

Only needed to reproduce the paper's numbers.

1. **Get the datasets** (not vendored):
   - RedCode → `benchmarks/RedCode/dataset/RedCode-Exec/py2text_dataset_json/index{N}_30_codes_full.json`
   - SafeAgentBench → `benchmarks/SafeAgentBench/dataset/{safe,unsafe}_detailed_1009.jsonl`
2. `export OPENAI_API_KEY=...` — `code_agent.py` hardcodes `gpt-4o`.
3. Fix the working-directory problem from §2 (flat imports vs. relative data paths).
4. `code_agent.py` writes to `expres/code/python/`, which already contains the
   authors' results — **back them up first** or you'll overwrite the baseline
   you're trying to compare against.
5. `code_agent.py` has a `break` inside its per-case loop (`src/code_agent.py:59`)
   that stops after the first case. Intentional or not, check it before you
   conclude anything from a run.

Budget real money for API calls: 27 indices × 30 programs × several agent steps.

---

## 8. Suggested first commits on this fork

1. `.gitignore` for `.venv/`, `__pycache__/`, `*.pyc`, `.DS_Store` *(done)*
2. `RUNNING.md` + `smoke_test.py` + `tools/audit_rules.py` *(done)*
3. The `Rule.triggered` fix *(applied, uncommitted)*
4. A `pytest` suite + CI, starting from `smoke_test.py`

Being able to say "the original had no passing tests; ours has a green suite and
a verification gate" is a real engineering contribution for the thesis.
