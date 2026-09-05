# Running and reading the tests

Everything here runs **offline** — no OpenAI key, no benchmark datasets, no
network. A scripted `FakeListLLM` drives the agent and a recording stub replaces
`PythonREPL`, so the suite finishes in well under a second.

> **Run everything from the repo root** — `cd` into `AgentSpec/` first. The venv
> lives at `AgentSpec/.venv`, so `.venv/bin/pytest` only resolves from there.
> `conftest.py` also locates `src/` relative to itself.

---

## 1. Quick start

```bash
cd /path/to/AgentSpec
make test
```

`make` wraps the common commands so you never have to type a venv path:

| Target | Does |
|---|---|
| `make test` | the whole suite |
| `make test-verbose` | enforcement tests with the agent trace |
| `make test-why` | why each grammar xfail fails |
| `make test-parsing` | grammar probes with the real ANTLR errors |
| `make audit` | parse-check every shipped `.ar` / `.rule` file |
| `make profile` | time the suite and report per-phase latency |
| `make spikes` | run the Cedar spikes (S1.1, S1.2) |
| `make ui` | the test bench — try rules interactively (see `ui/README.md`) |
| `make venv` | build `.venv` from scratch with pinned deps |
| `make help` | list all targets |

The equivalent raw command, if you prefer:

```bash
.venv/bin/pytest -q
```

Expected:

```
.................xxxxxxxx                                                [100%]
51 passed, 13 xfailed in 0.19s
```

`x` = **xfail**, an *expected* failure. The 13 xfails are recorded defects we
deliberately recorded; they are not broken tests. See §4.

Exit code `0` means green. If pytest isn't found:

```bash
.venv/bin/pip install pytest
```

---

## 2. Command cheat-sheet

| Command | What you get |
|---|---|
| `.venv/bin/pytest -q` | one line, pass/fail counts |
| `.venv/bin/pytest -v` | every test name and its verdict |
| `.venv/bin/pytest -rxX` | **the reason behind every xfail** ← most useful |
| `.venv/bin/pytest --runxfail` | run the xfails for real and show the actual errors |
| `.venv/bin/pytest -s` | let `print()` and agent traces reach the terminal |
| `.venv/bin/pytest -x` | stop at the first failure |
| `.venv/bin/pytest --tb=long` | full tracebacks (default is `short`) |
| `.venv/bin/pytest --collect-only -q` | list tests without running them |
| `.venv/bin/pytest -k skip` | run only tests whose name matches `skip` |
| `.venv/bin/pytest --lf` | re-run only what failed last time |

Combine freely: `-vv -rxX -s` is the "show me everything" setting.

---

## 3. `test_enforcement.py` — watching enforcement happen

By default the agent runs silently. Set `AGENTSPEC_VERBOSE=1` **and** pass `-s`
(pytest captures stdout otherwise, so one without the other shows nothing):

```bash
AGENTSPEC_VERBOSE=1 .venv/bin/pytest -s -q tests/test_enforcement.py
```

### A blocked action

```bash
AGENTSPEC_VERBOSE=1 .venv/bin/pytest -s -q \
  tests/test_enforcement.py::test_destructive_action_is_blocked
```

```
> Entering new ControlledAgentExecutor chain...
python_repl                       ← rule event being matched
destuctive_os_inst                ← predicate being evaluated
action stopped by rule @block_file_deletion
trigger
    python_repl
check
    destuctive_os_inst
enforce
    stop
end

> Finished chain.
.
1 passed in 0.01s
```

No `>>> TOOL REACHED` line: the tool was never called. That absence is the
assertion — `assert tool_calls == []`.

> The bare `python_repl` / `destuctive_os_inst` lines are stray `print()` calls
> in `src/interpreter.py` (upstream's, not ours). Left in place because they
> happen to show which rule and predicate were evaluated. Silence them by
> deleting the prints at `src/interpreter.py:59` and `:61` if they annoy you.

### An allowed action

```bash
AGENTSPEC_VERBOSE=1 .venv/bin/pytest -s -q \
  tests/test_enforcement.py::test_benign_action_is_allowed
```

```
> Entering new ControlledAgentExecutor chain...
python_repl
destuctive_os_inst
Thought: I should use the tool.
Action: python_repl
Action Input: print(6 * 7)
  >>> TOOL REACHED: 'print(6 * 7)'

Observation: OK
Thought: I have the answer.
Final Answer: 42

  --- outcome ---
  tool calls        : ['print(6 * 7)']
  final output      : '42'
  intermediate steps: 1
    [1] action     : python_repl('print(6 * 7)')
        observation: 'OK'
```

The rule was evaluated (`destuctive_os_inst`) and declined to fire. This is the
false-positive check — a guard that blocks everything would still pass the
destructive test above.

### Reading a full run

Each test's block is labelled, and the header names the rules in play:

```
========================================================================
=== test_no_rules_means_no_interference
========================================================================
  rules loaded      : NONE - nothing can fire
```

That `rules loaded` line is the first thing to check when an action you
expected to be blocked wasn't. `test_no_rules_means_no_interference` runs the
same `os.remove(...)` as Scenario A and lets it straight through **on purpose**
— it's the control. Without it, a Scenario A pass wouldn't prove the *rule* did
the blocking.

Two other tells that no rule was consulted: no `python_repl` /
`destuctive_os_inst` debug lines (upstream prints those only while evaluating a
rule), and `intermediate steps: 1` rather than `0`.

`Observation: OK` never means code ran. The tool is the recording stub from
`conftest.py`, which appends to `tool_calls` and returns the literal string
`"OK"` — so no file is ever deleted, in any test.

### The `--- outcome ---` block

Every enforcement test ends with `show(result, tool_calls)` from `conftest.py`,
which prints the three things the assertions actually look at: what reached the
tool, the final output, and the intermediate steps.

It exists because **the chain trace is not always enough**. `skip` is invisible
in it: `ControlledAgentExecutor._iter_next_step` yields its `AgentStep` directly
without calling `run_manager.on_agent_action`, so `verbose=True` never prints
the skipped action. The only evidence is in `intermediate_steps`:

```bash
AGENTSPEC_VERBOSE=1 .venv/bin/pytest -s -q \
  tests/test_enforcement.py::test_enforce_skip_drops_the_action_but_continues
```

```
> Entering new ControlledAgentExecutor chain...
Thought: I have the answer.
Final Answer: 42            ← the chain trace shows no sign a skip happened

  --- outcome ---
  tool calls        : NONE (blocked before the tool)
  final output      : '42'
  intermediate steps: 1
    [1] action     : python_repl('print(6 * 7)')
        observation: 'after the enforcement of rule:\nrule @always_skip\n...'
```

(That observability gap is worth carrying into the Cedar engine as something to
fix, not copy.)

### The three enforcement modes side by side

```bash
AGENTSPEC_VERBOSE=1 .venv/bin/pytest -s -v -k "enforce_" tests/test_enforcement.py
```

| Mode | Tool reached? | Run continues? | Evidence |
|---|---|---|---|
| `stop` | no | no — run ends | `output` contains `stopped by`; **0** steps |
| `skip` | no | yes | **1** step, observation says `skipped by user` |
| `none` | **yes** | yes | tool in `tool_calls`; rule matched but didn't intervene |

---

## 4. `test_rule_parsing.py` — seeing *why* the grammar rejects things

### The reasons, without running anything

```bash
.venv/bin/pytest -rxX -q tests/test_rule_parsing.py
```

```
XFAIL ...[comment] - no comment token in AgentSpec.g4; every .ar file uses // comments
XFAIL ...[predicate outside token list] - PREDICATE is a closed 36-alternative token,
      so adding a check requires regenerating the parser (README documents this)
XFAIL ...[capitalised True] - toolemu.ar writes `check True`; the grammar only accepts lowercase
XFAIL ...[dotted trigger] - toolemu.ar uses Toolkit.Action triggers; event is a bare IDENTIFIER
XFAIL ...[trigger alternation] - toolemu.ar uses | to share one rule across tools; no such operator
XFAIL ...[multi-word trigger] - embodied.ar triggers on robot verbs like `turn on`
XFAIL ...[conjunction with &] - apollo/*.rule uses & to conjoin predicates
XFAIL ...[llm_self_examine] - the README documents llm_self_examine; the grammar
      implements llm_self_reflect -- the docs and the language disagree
```

### The actual ANTLR errors

`--runxfail` runs the expected-failure tests as ordinary tests, so you see the
real diagnostic:

```bash
.venv/bin/pytest --runxfail -q "tests/test_rule_parsing.py::test_known_grammar_limitation[dotted trigger]"
```

```
E       AssertionError:
E              1 | rule @r
E              2 | trigger
E              3 |     Gmail.SendMail
E              4 | check
E              5 |     true
E              6 | enforce
E              7 |     stop
E              8 | end
E
E           1 syntax error(s):
E             - L3:9 mismatched input '.' expecting 'check'
```

Numbered listing on top, ANTLR's complaint underneath. Drop the `::...` suffix
to see all nine at once.

### Trying your own rule

Fastest loop — no test file needed:

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0, 'tests'); sys.path.insert(0, 'src')
from test_rule_parsing import parse_errors
print(parse_errors(open('/dev/stdin').read()) or 'parses cleanly')
" <<'EOF'
rule @my_rule
trigger
    python_repl
check
    involve_system_file
enforce
    user_inspection
end
EOF
```

For a whole file or the shipped corpus, use the audit tool instead:

```bash
.venv/bin/python tools/audit_rules.py src
```

---

## 5. Running one test, or a few

```bash
# one file
.venv/bin/pytest tests/test_enforcement.py

# one test
.venv/bin/pytest tests/test_enforcement.py::test_enforce_skip_drops_the_action_but_continues

# one parametrised case — quote it, the brackets are shell globs
.venv/bin/pytest "tests/test_rule_parsing.py::test_known_grammar_limitation[comment]"

# one class
.venv/bin/pytest tests/test_enforcement.py::TestTriggerMatching

# by name fragment
.venv/bin/pytest -k "trigger and not grammar" -v
```

---

## 6. When something fails

```bash
.venv/bin/pytest -x -vv --tb=long
```

- `-x` stops at the first failure so you aren't reading a wall of noise.
- `-vv` stops pytest truncating the assertion diff.
- `--pdb` drops into a debugger at the failure point.

**`XPASS(strict)` is a real failure, and it's on purpose.** The 13 xfails are
`strict=True`. If you fix the grammar (plan.md **S3.1**), they start passing and
pytest reports:

```
FAILED tests/test_rule_parsing.py::test_known_grammar_limitation[dotted trigger]
       - [XPASS(strict)] toolemu.ar uses Toolkit.Action triggers; ...
```

That is the suite telling you to move that case from `LIMITATIONS` into
`SUPPORTED` in the same commit — so the file can't drift out of date with the
grammar.

---

## 7. What each file covers

**`conftest.py`** — fixtures shared by both files.

- puts `src/` on `sys.path` (the repo has no package layout; modules import each
  other flatly, e.g. `from rule import Rule`)
- `recording_tool` — a stub named `python_repl` that appends to `tool_calls`
  and returns `"OK"`. Deliberately *not* the real `PythonREPL`: these tests ask
  whether the tool was **reached**, and running generated code to find out would
  make the destructive cases actually destructive.
- `agent_factory(rule_texts, llm_script)` — builds a `ControlledAgentExecutor`
  with a scripted LLM.
- `react_script(...)` — a two-turn ReAct script (call the tool, then finish).

**`test_enforcement.py`** (11 tests)

| Test | Asserts |
|---|---|
| `test_destructive_action_is_blocked` | Scenario A — `os.remove` is stopped, tool never runs |
| `test_benign_action_is_allowed` | Scenario B — arithmetic gets through (no false positive) |
| `test_no_rules_means_no_interference` | empty rule set ⇒ plain `AgentExecutor` |
| `test_enforce_stop_ends_the_run` | `stop` — no tool, no steps, run terminates |
| `test_enforce_skip_drops_the_action_but_continues` | `skip` — no tool, one step, run continues |
| `test_enforce_none_lets_the_action_through` | `none` — rule matched, tool still ran |
| `test_first_matching_rule_decides` | rule **order** changes the verdict (see below) |
| `TestTriggerMatching` (4) | `Rule.triggered` survives `None` and `dict` inputs |

The mode tests use `check true` so they isolate the enforcement outcome from
predicate logic. `test_first_matching_rule_decides` documents rather than
endorses: a permissive rule ahead of a restrictive one wins purely by position.
That order dependence is one of the properties Cedar removes — `forbid` always
wins, whatever the order (plan.md **S2.8**).

**`test_spikes.py`** (13 tests) — pins the Cedar findings in `docs/spikes.md`:
that `@advice` is reachable via `policies_to_json_str()` and *not* via
`id_annotations_by_reason`, that the annotation ids join to
`diagnostics.reasons`, and that the advice lattice is order-independent. Skipped
if `cedarpy` is missing.

**`test_fail_open.py`** (15 tests) — the four ways a malformed rule gets past load
time: silent acceptance, silent truncation of a dotted trigger, an `AttributeError`
that depends on a comment's word count, and predicates named in rules but never
registered. Four strict xfails say what should happen; they turn green at S2.5.

**`test_ui_examples.py`** (13 tests) — every worked example in the test bench must
produce the verdict its help page claims, so the docs can't drift from behaviour.
Also covers the bench's path guard.

**`test_rule_parsing.py`** (15 tests) — 6 things the grammar accepts, 9 it
rejects. Every rejected case is syntax that appears in the repo's own rule files
or README, which is why 21 of the 42 shipped rules don't parse
(`tools/audit_rules.py`).

---

## 8. Gotchas

| Symptom | Cause |
|---|---|
| `ModuleNotFoundError: No module named 'rule'` | ran pytest from outside the repo root; `conftest.py` resolves `src/` relative to itself, so run from the root |
| `AGENTSPEC_VERBOSE=1` prints nothing | you also need `-s` — pytest captures stdout by default |
| `no tests ran` with a `[...]` test id | shell expanded the brackets; quote the id |
| `pytest: command not found` | use `make test`, or `.venv/bin/pytest`, or activate the venv first |
| `zsh: no such file or directory: .venv/bin/pytest` | you're not in the repo root — `cd` into `AgentSpec/` |
| stray `python_repl` / `destuctive_os_inst` lines | upstream debug prints in `src/interpreter.py`, harmless |
