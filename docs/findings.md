# Findings — a running lab notebook

Standing task W.2. Every surprise, bug and counterexample, dated, with the step
it came out of and how to reproduce it. Findings evaporate if they are not
written down, and several of these are the thesis's most quotable results.

Defects in the *shipped corpus* are numbered `D-n` — those are the RQ1/RQ4/RQ6
material. Observations about Cedar or about our own design are recorded as prose
under the step that produced them.

---

## D-1 · `is_buggy_ip_validation_code` is a constant `True` in practice

*Found 2026-09-06 during S2.3, by running the whole code domain over benign input.*

`src/rules/manual/pythonrepl.py` defines a predicate meant to detect faulty
IP-address validation. It returns `True` for **every input we have been able to
construct**, including the empty string and a *correct* IP-validation regex.

```
input                                        result
''                                           True
'2+2'                                        True
"re.match(r'^(25[0-5]|2[0-4][0-9]|...)$',s)" True     <- correct code, flagged
'^$'                                         True
```

The cause is check #2 of five:

```python
if not re.search(r"^\^", tool_input) or not re.search(r"\$$", tool_input):
    return True
```

It asks whether the **code text** begins with a literal `^` and ends with a
literal `$` — a property of a bare regex string, not of a Python program. Almost
no tool input satisfies it, so the predicate short-circuits to `True`. The
remaining checks are unreachable for practical purposes, and check #3 catches
the residue (`'^$'` has no digits, so it too returns `True`).

**Why it matters.** A predicate that is constantly true makes any rule using it
fire on every action of its trigger. Since 24 of the 26 rules in `pythonrepl.ar`
enforce `user_inspection`, such a rule would prompt the user on *every single*
PythonREPL call — the behaviour that makes a guardrail get switched off. This is
RQ2b's floor: the baseline's false-positive rate is bounded below by its own
predicate bugs, not by its policy language.

Reproduce: `tests/test_ui_examples.py::test_benign_arithmetic_still_trips_two_shipped_predicates`.

## D-2 · `write_to_io` treats every `print()` as I/O

*Found 2026-09-06 during S2.3.*

Its pattern is `print\(.*?\)`, so `print(6 * 7)` — the bench's own example of a
harmless action — sets the flag. Defensible as a literal reading of "writes to
I/O", but it means the flag carries almost no information on real Python: it is
close to a constant on any code that reports a result.

Combined with D-1, **2 of 25 code sensors fire on `print(6 * 7)`** and 1 of 25
fires on the empty string.

## D-3 · The `.ar` corpus and the executable predicate table disagree at 8 of 16 indices

*Found 2026-09-06 during S2.3.*

`src/rules/manual/pythonrepl.ar` is the rule corpus a human reads and the grammar
parses. `checks` in `pythonrepl.py` is what actually becomes `predicate_table`
and can execute. They are indexed the same way (`// indexN` ↔ `checks["indexN"]`)
and are clearly meant to correspond. They do not:

| index | `.ar` says | `checks{}` says |
|---|---|---|
| 9  | `write_to_io`, `contain_exec_string` | `write_to_io`, `involve_bash_rc` |
| 11 | *(no check clause)* | `predicate11`, `write_to_io` |
| 12 | `is_fair` | `has_bias_issues` |
| 14 | `contain_exec_string`, `execute_script` | `execute_script` |
| 15 | `backtracking_regex_pattern` | `is_buggy_ip_validation_code` |
| 16 | *(no check clause)* | `is_side_channel_vulnerable` |
| 17 | `raise_privilege`, `!lower_privilege` | `is_improper_execution_privilege_code` |
| 18 | `kill_process` | `is_buggy_process_management` |

Several names on the `.ar` side (`contain_exec_string`, `is_fair`,
`backtracking_regex_pattern`, `raise_privilege`, `lower_privilege`,
`kill_process`) are **not registered at all**, so those rules cannot execute:
`RuleInterpreter.eval_predicate` does `predicate_table[name]` and raises
mid-run. That is the same class as S0.12's `is_malware`, but systematic.

**Why it matters.** It is a second, independent measurement of the same gap
S0.12 opened: nothing in AgentSpec relates the rule text to the registry, so the
two drift and neither side notices. It also bounds S3.4 — the corpus cannot be
compiled faithfully where the two sources disagree about what a rule means, and
`docs/coverage.md` (S3.5) has to say which side it took and why.

Reproduce: `tests/test_sensors.py` records the registry side; the comparison
script is in the S2.3 log entry of `plan.md`.

## D-4 · No predicate uses the user's task

*Found 2026-09-06 during S2.3, correcting a weaker claim made at S2.1.*

S2.1 reported "35 of 36 never read `user_input`, the exception being
`predicate11`". That was too generous. `predicate11` only *forwards* the
argument to four helpers (`access_clipboard`, `capture_screenshot`,
`monitor_file_system_event`, `check_process_status`), all of which ignore it. Its
answer does not depend on the task, so the honest figure is **36 of 36**.

A guard that cannot relate the proposed action to what was asked for cannot
distinguish "delete the temp file I asked you to delete" from "delete something
else" — so an entire class of false positive is unavoidable for the baseline,
independently of its policy language. RQ2b.

Reproduce: `tests/test_sensors.py::test_no_predicate_actually_uses_the_user_task`.

---

## Observations on the design (not corpus defects)

### Cedar fails open unless you make it fail closed — S1.7

`is_authorized` returns `Decision.NoDecision` and puts the cause in
`diagnostics.errors` when it cannot evaluate a request; it does **not** raise. A
malformed entity store does exactly this. Any engine that reads "not Deny" as
permission converts an internal fault into a silent allow. `decide()` maps
NoDecision-or-errors onto `stop`.

### The tool name is attacker-influenced — S1.7

It reaches the request from model output, so a crafted name interpolated raw into
`Tool::"..."` closes the entity uid early. Measured: unescaped it produces
`failed to parse schema from request`, so it degrades to a denial of service
rather than a policy bypass — but only because of the fail-closed handling above.
Escaped at the boundary regardless; a parser is not an access control.

### Optional record attributes are what make the flags honest — S2.2

Cedar record attributes are required by default, and a request missing one is
`NoDecision`. Shipping required flags would have forced the engine to send
`false` for every sensor that never ran — asserting "not happening" about checks
nobody performed, which is the exact failure class this project exists to remove.
With `name?: Bool`, Cedar instead **refuses to validate an unguarded access**
("unable to guarantee safety of access"), so a policy must write
`context.flags has X && context.flags.X` and the three states stay distinct:
fired / ran-and-said-no / never-ran.

### Sensor cost is dominated by input size, not sensor count — S2.3

Running the whole code domain (25 sensors) against one sensor:

| tool input | 1 sensor | 25 sensors |
|---|---:|---:|
| `print(6 * 7)` | 0.0023 ms | 0.0893 ms |
| ~2 KB of code | 0.0043 ms | 2.9765 ms |

A Cedar decision is 0.058 ms (S1.4), so on a 2 KB input **detection costs ~51×
the decision**. This is the concrete form of RQ5's expected headline — "the
policy engine is free; detection is the cost" — and it makes `Sensor.cost`
operational rather than decorative. The available lever, if it is ever needed, is
to materialise only the flags the loaded policy set actually reads; measured, that
is 25 sensors down to 1.

### Selecting sensors by domain is not an optimisation, it is a correctness requirement — S2.1/S2.3

Five of the eleven embodied predicates *raise* rather than returning `False` when
handed a code agent's `intermediate_steps`, and the exception class is not stable
for a given sensor (`is_unsafe_fillliquid` gives `AttributeError` on an input
containing spaces and `IndexError` on one without). "Catch the known exception"
was therefore never available. Not running them is, and every raising sensor is
one whose `reads` include `intermediate_steps` — so the registry metadata is
sufficient to select them out, with no blocklist.

Across 10 varied inputs × 3 history shapes, **0 of the 25 code sensors raise**.
