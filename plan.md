# 90-day execution plan — Cedar policy engine for AgentSpec

**Branch:** `dev-foued` · **Started:** 2026-09-04 · **Deadline:** 2026-12-02 (Day 90)
**Goal:** replace AgentSpec's ad-hoc rule DSL with a Cedar-based policy engine that
(a) reasons over execution *paths*, (b) supports non-binary enforcement, and
(c) can be formally analysed — see [`docs/AgentSpec-Cedar-Thesis-Plan.md`](docs/AgentSpec-Cedar-Thesis-Plan.md).

---

## How we use this file

- Every step has a checkbox and an **acceptance test** — an objective way to know it's done.
- When a step is finished: change `- [ ]` to `- [x]`, append `✅ YYYY-MM-DD` to the line,
  and add a one-line entry to the **Progress log** at the bottom.
- If a step is skipped or descoped, change it to `- [~]` and write why in the log.
- Steps inside a sprint are ordered — do them top to bottom.
- ⭐ marks the two sprints that carry the thesis contribution. **Protect their time.**
  If we fall behind, cut Sprint 3 (compiler) and Sprint 6b (portability) first.

**Current position:** Sprint 2, Step S2.8 (order independence — free thesis result).

---

## Sprint 0 — Foundation & hygiene · Days 1–7 (Sep 4 – Sep 10)

Goal: a clean, tested, reproducible base to build on.

- [x] **S0.1** Create branch `dev-foued`. ✅ 2026-09-04
- [x] **S0.2** Add `.gitignore` for `.venv/`, `__pycache__/`, `*.pyc`, `.DS_Store`. ✅ 2026-09-04
- [x] **S0.3** Set up the venv with pinned LangChain 0.3.x deps (see `RUNNING.md` §2). ✅ 2026-09-04
      *Accept:* `cd src && ../.venv/bin/python -c "import interpreter, controlled_agent_excector"` prints no error.
- [x] **S0.4** Fix the `Rule.triggered` crash on `AgentFinish` (None/dict tool inputs). ✅ 2026-09-04
      *Accept:* Scenario B of `smoke_test.py` completes instead of raising `AttributeError`.
- [x] **S0.5** Write `smoke_test.py` — offline enforcement test, no API key. ✅ 2026-09-04
      *(Superseded by S0.8: converted into `tests/` and the file removed.)*
- [x] **S0.6** Write `tools/audit_rules.py` — parse audit of the shipped rule corpus. ✅ 2026-09-04
      *Accept:* `.venv/bin/python tools/audit_rules.py src` emits the three Markdown tables.
- [x] **S0.7** Write `RUNNING.md` — setup, testing, known breakages. ✅ 2026-09-04
- [x] **S0.8** Convert `smoke_test.py` into a real pytest suite at `tests/`. ✅ 2026-09-04
      `tests/conftest.py` (recording tool stub + scripted-LLM agent factory),
      `tests/test_enforcement.py` (11 tests), `tests/test_rule_parsing.py` (14 tests).
      *Accept:* ✅ `.venv/bin/pytest -q` → **17 passed, 8 xfailed**; 25 tests collected.
- [x] **S0.9** Add `requirements-dev.txt` and a GitHub Actions workflow. ✅ 2026-09-04
      Two jobs: `test` (matrix 3.11/3.12/3.13, all required) and `audit` (publishes
      the rule-corpus parse state to the run summary on every push, feeding S0.10).
      Dropped `langchain-community` and `langchain-experimental` from the test path
      — `FakeListLLM` is in `langchain-core`, so CI installs 43 packages in ~5s
      instead of pulling SQLAlchemy and aiohttp.
      *Accept:* ✅ [run #1](https://github.com/Beatrice-Beacco/AgentSpec/actions/runs/33972706004)
      green on all four jobs in ~20s each.
- [x] **S0.10** Freeze the audit as `docs/baseline-audit.md`. ✅ 2026-09-05
      `tools/audit_rules.py` now emits a provenance header (date, commit SHA, branch,
      Python and ANTLR versions, dirty-tree flag). `make audit-freeze` regenerates it.
      *Accept:* ✅ committed with the SHA it was generated from.
- [x] **S0.11** Latency instrumentation behind `AGENTSPEC_PROFILE=1`. ✅ 2026-09-05
      `src/profiling.py` + hooks in `_iter_next_step` and `verify_and_enforce`.
      `make profile` reports, `make profile-freeze` writes `docs/baseline-latency.md`.
      *Accept:* ✅ 31 JSONL lines, four timings each.
      **Result: 77.6% of guard time is `rule_parse`** — AgentSpec re-lexes and
      re-parses every triggered rule's text on every action. Only 18.4% is actually
      evaluating predicates. Cedar parses a `PolicySet` once (feeds RQ5 / S2.9).
- [x] **S0.12** Record the fail-open behaviour as xfail tests. ✅ 2026-09-05
      `tests/test_fail_open.py` — 4 strict xfails for what *should* happen, 7 passing
      tests recording what does. Turns green at S2.5; this is RQ6.
      *Accept:* ✅ `test_malformed_rule_is_rejected` xfails with the cause in its reason.
      Found **four** distinct failure modes, not one — see the log below.

- [x] **S0.13** Build the **test bench** — a local web UI for exercising rules. ✅ 2026-09-04
      `make ui` → <http://127.0.0.1:5000>. Edit rules with live parse-checking, load
      from the shipped corpus, set a user task + proposed action, run it, and see the
      verdict plus a per-rule "why" panel (trigger matched? each predicate's value?
      which enforcement?). Includes a help page with 8 worked examples and a
      predicate prober. Driven by `FakeListLLM`, so no API key and fully
      deterministic — usable as a regression tool.
      *Accept:* ✅ all 8 examples produce their documented verdict, asserted by
      `tests/test_ui_examples.py`.
      **Use this after every step from here on** (see W.4).

**Sprint 0 exit:** green pytest suite, CI running, baseline audit + latency frozen in `docs/`.

---

## Sprint 1 — Cedar spike & walking skeleton · Days 8–16 (Sep 11 – Sep 19)

Goal: the smallest possible end-to-end path where **Cedar** makes the decision.
Resolve every unknown here, before writing real code.

- [x] **S1.1** `spikes/hello_cedar.py` — the smallest Cedar decision. ✅ 2026-09-05
      Written in the PARC shape the thesis proposes (`Agent` / `invoke` / `Tool` /
      `context.flags`), not the Cedar docs' example, so it is a real precursor to
      `agentguard/request.py`. `make spike-hello`.
      *Accept:* ✅ Allow for `print(6*7)`, Deny for `os.remove(...)`.
- [x] **S1.2** ⚠️ **The annotation question — answered.** ✅ 2026-09-05
      `diagnostics.id_annotations_by_reason` returns **only `@id`**, so the plan's
      first choice fails. `policies_to_json_str()` returns **every** annotation,
      keyed by the same synthetic ids `diagnostics.reasons` uses — so the join is
      direct. Decision recorded in [`docs/spikes.md`](docs/spikes.md); none of the
      three fallbacks the plan listed are needed. `make spike-annotations`.
      *Accept:* ✅ prints the advice for a denying policy and resolves the lattice.
- [x] **S1.3** Schema validation spike. ✅ 2026-09-05
      Eight cases: **five of six** malformed policies are rejected before any agent
      step runs (typo'd context attribute, typo'd entity attribute, type mismatch,
      unknown entity type, unknown action). AgentSpec catches none of them.
      **Settles S2.2:** a misspelled flag is *missed* under `Set<String>` and
      *caught* under a record of `Bool` — so S2.2 generates the record schema from
      the predicate registry. `make spike-validation`.
      *Accept:* ✅ prints each validation error.
- [x] **S1.4** Decision latency: 10k authorizations. ✅ 2026-09-05
      **0.0579 ms mean / 0.0772 ms p99** with a pre-parsed `PolicySet`; 0.1196 ms if
      you pass policy text each call (2× slower — the trap to avoid in
      `agentguard/engine.py`). `make spike-latency`.
      *Accept:* ✅ recorded in [`docs/spikes.md`](docs/spikes.md).
      A whole Cedar decision costs **less than AgentSpec spends on parsing alone**
      (0.1512 ms) and 3.3× less than its full guard path (0.1919 ms) — while doing
      more work: 3 policies, schema validation, order-independent result.
- [x] **S1.5** Write the first real schema `policies/schema.cedarschema` — just `Agent`,
      `Tool`, `action invoke`, and a `context` with `flags: Set<String>`. ✅ 2026-09-05
      Namespaced `AgentGuard` per thesis §C.2, so the skeleton is a precursor and not
      a throwaway. `tools/validate_policies.py` (`make validate`) is the load-time
      gate S2.5 will call; `tests/test_schema.py` pins six malformed-policy classes
      as rejected and the one known hole as still open.
      *Accept:* ✅ `test_hand_written_policy_validates` — and both verdicts are
      reachable through the real file, not just a validating string.
- [x] **S1.6** Write `policies/core.cedar` with two policies: a baseline `permit`, and a
      `forbid` for `destuctive_os_inst` carrying `@advice("stop")`. ✅ 2026-09-05
      The baseline is unconditional on purpose — a fail-closed one would change the
      verdicts S1.7 has to match, so it moves to S2.7 with the parity suite.
      `tools/validate_policies.py` grew an **annotation lint**: Cedar treats
      annotations as opaque strings, so a typo'd `@advice("stopp")` validates
      cleanly and then crashes the resolver.
      *Accept:* ✅ `make validate` green; `tests/test_core_policies.py` (13 tests)
      reaches both verdicts through the real file and carries `stop` back out.
- [x] **S1.7** Wire it in: `agentguard/executor.py` with `CedarControlledAgentExecutor`,
      one hard-coded sensor (`destuctive_os_inst`), behind an env flag `AGENTGUARD=cedar`. ✅ 2026-09-05
      Overrides exactly one method — `validate_and_enforce` — so the ReAct loop, the
      enforcement classes and the observation text are shared and a verdict difference
      is a difference in *deciding*. Seams for S2.1–S2.6 are marked in place.
      *Accept:* ✅ scenarios A and B (`smoke_test.py`'s, now
      `tests/test_enforcement.py`'s) pass under `AGENTGUARD=cedar` with the same
      verdicts; `tests/test_cedar_executor.py` (31 tests) runs the comparison itself
      rather than asserting it twice by hand.
      **`make test-cedar` forces the whole suite onto Cedar: 110/122 pass already.**
      The 12 failures are all legacy-rule tests the two-policy set cannot cover — the
      S2.7 worklist, measured rather than guessed.

- [x] **S1.8** Wire the bench's **Cedar decision** panel (currently a placeholder):
      show Allow/Deny and the raw `diagnostics` for the same input the legacy engine
      just ran, so the two are visible side by side. ✅ 2026-09-05
      Shows the decision, the enforcement outcome it resolves to, an agrees/differs
      badge against the legacy verdict, the materialised `context.flags`, and each
      determining policy with its `@advice` and `@source`. A decision, not a second
      agent run. The engine toggle and full compare mode stay with S2.10.
      *Accept:* ✅ example 1 → **Deny · resolves to STOPPED · agrees**, naming
      `@no_destructive_os_call`; example 3 → **Deny · differs — legacy said ALLOWED**.
      Pinned by `tests/test_ui_examples.py`.

**Sprint 1 exit:** ✅ 2026-09-05 — the same scenarios pass through either engine
(`make test-cedar`: 110/122 of the *whole* suite already), and the bench shows both
verdicts on one screen. Screenshot the bench on example 1 (agrees) and example 3
(differs) — the pair is the thesis figure, not just one of them.

---

## Sprint 2 — The engine · Days 17–34 (Sep 20 – Oct 7)

Goal: a real, tested `agentguard/` package. No hard-coding left.

- [x] **S2.1** `agentguard/sensors.py` — a registry wrapping all 36 predicates from
      `rules.manual.table.predicate_table`, each with metadata: name, domain
      (code/embodied/toolemu), cost hint, which flags it can set. ✅ 2026-09-06
      Metadata is **derived** from the predicates (AST for `reads`, defining module
      for `domain`, `reads` for `cost`), not hand-listed — so adding a predicate
      needs no edit here, which is what S2.2's "no hand-editing" depends on.
      `make sensors` prints the table. Cost scale is `input < history < model`.
      *Accept:* ✅ `len(SENSORS) == 36`; `tests/test_sensors.py` — 22 tests, each
      re-deriving independently rather than restating the module's own tables.
      ⚠️ **The third domain does not exist.** 25 code + 11 embodied; `toolemu.py` is
      an empty file and `terminal.py`'s 4 predicates are never merged into
      `predicate_table`. Carry into S3.4 and S6.3, which both assume otherwise.
- [x] **S2.2** `agentguard/schema.py` — generate `schema.cedarschema` **from** the sensor
      registry, so flags are a validated record-of-bools rather than free strings.
      Keep the `Set<String>` variant behind a flag so we can compare both (thesis §C.2). ✅ 2026-09-06
      `make schema` regenerates; `make validate` now **fails if the file on disk has
      drifted** from the registry, so a hand-edited schema cannot ship. The variant is
      recorded in the generated header and read back by the request builder, so the two
      cannot disagree. Both variants stay generatable for the §C.2 comparison.
      ⚠️ **The Bools are optional (`name?: Bool`), which the plan did not anticipate** —
      required attributes would force the request to carry all 36 flags or Cedar answers
      `NoDecision`, i.e. send `false` for 35 sensors that never ran. See the log.
      *Accept:* ✅ `tests/test_schema_codegen.py` (17 tests) adds a flag and regenerates
      with no template change; S1.5's "misspelled flag is missed" test has flipped to
      `test_a_misspelled_flag_is_now_caught`.
- [x] **S2.3** `agentguard/request.py` — materialisation: `RuleState → (Request, Entities)`.
      Runs sensors, builds principal/action/resource/context. ✅ 2026-09-06
      Sensors are now selected **by domain**, not by name — the hard-coded single
      sensor is gone and the whole 25-sensor code domain runs. A sensor that raises
      is recorded and its flag left *absent* (= "not evaluated"), and the engine
      stops rather than deciding on evidence it failed to gather.
      `make golden` regenerates the golden request; review its diff, it is what
      every policy sees.
      *Accept:* ✅ `tests/test_request.py` (13 tests) against
      `tests/golden/request_python_repl.json`.
      ⚠️ Running the whole domain immediately exposed **three corpus defects** —
      see [`docs/findings.md`](docs/findings.md) D-1…D-4.
- [x] **S2.4** `agentguard/advice.py` — the advice lattice
      (`stop > user_inspection > llm_self_reflect > skip > allow`), plus the rule that
      `substitute` only applies when it is the unique determining policy. ✅ 2026-09-06
      `resolve()` is **total** — every input yields a Resolution and anything it
      cannot make sense of lands on `stop`, because raising here would put an
      exception between the agent and its guard exactly when the guard matters.
      The lattice had been duplicated in `tools/validate_policies.py`; that copy is
      gone, and the lint now also rejects `@advice("substitute")` with no
      `@substitute_tool`.
      *Accept:* ✅ `tests/test_advice.py` — 208 tests: all **25 ordered pairs**, plus
      idempotence, commutativity, associativity and absorption, which is what makes
      order-independence (M2) a theorem rather than a hope.
      ⚠️ **Substitution is unreachable in the baseline** — findings D-5. Anything we
      build here is a capability *addition*, not an improvement on a measured
      baseline, and the write-up has to say so.
- [x] **S2.5** `agentguard/engine.py` — load policies, **validate against the schema at
      startup and refuse to start on failure**, evaluate, resolve advice. ✅ 2026-09-06
      Four startup checks, not one: Cedar's validator, the `@advice` lint (which until
      now only the CLI ran), `@id` traceability, and a **coverage check** — every flag
      a policy reads must be one the configured domain will actually materialise.
      *Accept:* ~~flip S0.12's xfails~~ → **`tests/test_fail_closed.py`** (20 tests),
      paired one-to-one with `test_fail_open.py`. The xfails are **deliberately not
      flipped**: they assert on `Rule.from_text`, so passing them means patching
      `src/rule.py` — and then every comparison in the thesis is against a baseline we
      repaired rather than against AgentSpec. Rationale written into both files.
      ⚠️ **Correction to S2.2:** the `has` guard reopens the misspelled-flag hole the
      record schema closed, and the guarded form is the only one Cedar accepts — so the
      coverage check, not the schema, is what closes it. See `docs/findings.md`.
      RQ6 written up there the day it went green.
- [x] **S2.6** `agentguard/enforcer.py` — map advice onto the existing `enforcement.py`
      classes (reuse them; don't rewrite). ✅ 2026-09-06
      The five lattice outcomes are applied by AgentSpec's own unmodified classes.
      Two need an adapter, both because the baseline is **broken**, not because we
      disagreed: `llm_self_reflect` returns a raw LangChain object and crashes the
      recursion (**D-6**), and `substitute` has no working class to reuse (**D-5**),
      so this is the one place we add behaviour. A redirect (re-plan or rewrite) is
      **guarded again**, bounded by `MAX_REDIRECTS` — otherwise `@substitute_tool`
      would be a way around the guard.
      *Accept:* ✅ `tests/test_enforcer.py` — one test per mode (six: five lattice +
      substitute), plus the fail-closed cases and three end-to-end runs.
      ⚠️ **D-7:** 40 of 61 `enforce` clauses in the corpus use one of the two outcomes
      that actually work.
- [x] **S2.7** Finish `agentguard/executor.py` — no hard-coding, feature-flag parity. ✅ 2026-09-06
      Policy directory and domain are now `$AGENTGUARD_POLICIES` / `$AGENTGUARD_DOMAIN`;
      nothing about the deployment is baked in. **Settled where policy lives**: ambient,
      not a constructor argument — a guard whose rule set the caller supplies is opt-in
      per construction site. Written up in `docs/findings.md`.
      *Accept:* ✅ `make test-cedar` → **417 passed, 15 skipped, 0 failed**.
      ⚠️ Read the criterion honestly. The 15 skips all have an AgentSpec *rule* as
      their subject; most are blocked on **S3.3** (no compiler, nothing to decide on),
      and **two can never pass** — they assert order dependence, which the lattice
      removes by construction. Every test now either passes on both engines or carries
      a reason for belonging to one. `test_no_rules_means_no_interference` was made
      genuinely engine-agnostic, which is the ambient-policy question in executable form.
- [ ] **S2.8** Property test: **order independence.** Shuffle the policy set 100× and
      assert the verdict never changes. Then do the same with AgentSpec's rule list and
      show that it *does* change.
      *Accept:* `tests/test_order_independence.py` green for Cedar, and a documented
      counterexample for the legacy engine in `docs/findings.md`.
      *(This is a free, high-value thesis result. Don't skip it.)*
- [ ] **S2.9** Re-run the latency instrumentation with the Cedar engine.
      *Accept:* `expres/latency/cedar.jsonl`; sensors vs. decision split recorded.

- [ ] **S2.10** Bench: add an **engine toggle** (legacy ⇄ cedar) and render the
      resolved advice plus the policy ids from `diagnostics.reasons`. Add a
      "compare both" mode that runs one input through both engines and diffs the
      verdicts — this is how RQ1/RQ3 disagreements get found by hand.
      *Accept:* toggling the engine on example 1 shows both verdicts and the
      policies responsible.

**Sprint 2 exit:** `agentguard/` is the real engine, both engines pass the same suite,
RQ5 and RQ6 have preliminary numbers.

---

## Sprint 3 — AgentSpec → Cedar compiler · Days 35–46 (Oct 8 – Oct 19)

Goal: bring the existing rule corpus across automatically. **Cuttable if behind.**

- [ ] **S3.1** Fix the grammar defects found in the audit, in `src/spec_lang/AgentSpec.g4`:
      `//` and `/* */` comments; `&` and `|` in `check`; dotted and multi-word triggers;
      `IDENTIFIER` predicates instead of the closed 36-alternative token; align
      `llm_self_examine` / `llm_self_reflect`.
      ⚠️ Needs Java to regenerate the parser: `cd src && bash run.sh`.
      *Accept:* `tools/audit_rules.py` reports **0 parse failures** across the corpus.
- [ ] **S3.2** Fix `src/spec_lang/rule_examples/*.ar` (they use a dead older syntax) so
      the repo's own unit test passes, or replace the fixtures.
      *Accept:* `pytest` + `python -m unittest spec_lang.test_parse` both green.
- [ ] **S3.3** `agentguard/compile.py` — an ANTLR listener implementing the mapping table
      in thesis plan §C.6 (trigger→resource, check→context conditions,
      enforce→effect + `@advice`).
      *Accept:* compiling the smoke-test rule yields a policy that produces an identical verdict.
- [ ] **S3.4** Compile the whole corpus: 42 shipped rules + the LLM-generated ones in
      `src/rules/llm/generated_rules-{o1,4o}.jsonl`.
      *Accept:* `policies/generated/` populated; all pass `validate_policies()`.
- [ ] **S3.5** Write `docs/coverage.md`: how many rules compiled cleanly / with warnings /
      not at all, **with an analysis of every failure**. Failures are findings.
      *Accept:* table + prose; this is thesis RQ1.

**Sprint 3 exit:** RQ1 answered with a number.

---

## ⭐ Sprint 4 — Path sensitivity · Days 47–64 (Oct 20 – Nov 6)

Goal: the headline contribution — catching harmful *paths*, not just harmful calls.

- [ ] **S4.1** Design the taint vocabulary. Start small: `read_secret`, `read_system_file`,
      `fetched_untrusted`, `wrote_executable`, `escalated_privilege`, `user_approved_<cap>`.
      Write it up in `docs/taint-model.md` with the justification for each.
- [ ] **S4.2** Extend the schema with the `Session` entity (`taints`, `approved`,
      `allowed_hosts`, `step`) and reference it from `Agent`.
      *Accept:* a policy reading `principal.session.taints` validates.
- [ ] **S4.3** `agentguard/session.py` — lifecycle: create at task start, update after
      each observation, serialise into the entity store.
      *Accept:* `tests/test_session.py` shows taints accumulating across a 3-step run.
- [ ] **S4.4** Write ≥8 path-sensitive policies in `policies/paths.cedar`:
      exfiltration (read secret → outbound POST), untrusted-download → execute,
      approval-then-scope-creep, irreversible-action-after-failed-precondition.
      *Accept:* each has a test that passes on the harmful path and does **not** fire on
      the benign prefix.
- [ ] **S4.5** ⚠️ **Build the multi-step benchmark.** ~30 scenarios where every individual
      step is benign but the sequence is harmful. Existing benchmarks barely test this —
      that's the point, and it's an artifact contribution.
      Store as `benchmarks/paths/cases.jsonl` with a documented schema.
      *Accept:* 30 cases, each with a harmful trajectory and a benign near-miss twin.
      *Mitigate the self-authoring bias: derive as many as possible from real incident
      reports / CVEs, and record the provenance of each case.*
- [ ] **S4.6** Run both engines over the new benchmark.
      *Accept:* `docs/findings.md` has the table: legacy AgentSpec detection rate vs. ours,
      split by "single-action risky" and "path risky". **This is RQ3 — the headline.**
- [ ] **S4.7** Formalise the expressiveness claim: which fragment of LTL-over-finite-traces
      do the session attributes capture, and what does the finite abstraction lose?
      *Accept:* one page in `docs/taint-model.md`. Be honest about the limits.

- [ ] **S4.8** Bench: a **session/taint viewer** — show the taint set accumulating
      across the steps in the "Prior steps" box, so a path-sensitive policy can be
      debugged visually rather than by reading JSON.
      *Accept:* loading a multi-step exfiltration case shows `read_secret` appearing,
      then the policy firing on the later POST.

**Sprint 4 exit:** cases the original provably cannot catch, that ours does, with numbers.

---

## ⭐ Sprint 5 — Formal verification · Days 65–74 (Nov 7 – Nov 16)

Goal: prove things about the policy set that no prior agent-guardrail system can state.

- [ ] **S5.1** Install the toolchain: `cedar-policy-symcc` + **cvc5 1.3.1**.
      Do it in Docker — `docker/verify.Dockerfile` — so it's reproducible and doesn't
      pollute the machine.
      *Accept:* the crate's own example runs inside the container.
- [ ] **S5.2** `tools/verify.py` — drive symcc from Python over our policy sets.
      *Accept:* runs and reports for one property.
- [ ] **S5.3** **Equivalence:** prove the compiled policies (S3.4) are equivalent to the
      hand-written ones. This validates the compiler.
      *Accept:* equivalence proved, or a counterexample that exposes a compiler bug (fix it).
- [ ] **S5.4** **Shadowing / subsumption:** find policies subsumed by others — dead rules
      in the shipped corpus.
      *Accept:* a list, with the AgentSpec rules they came from.
- [ ] **S5.5** **Never-errors:** prove no policy can throw at runtime.
- [ ] **S5.6** **Coverage:** find requests no `permit` covers — the fail-closed surface.
- [ ] **S5.7** Write `docs/findings.md` §verification: **≥3 real defects found in the
      shipped corpus by automated analysis that no AgentSpec tooling could find.**
      *Accept:* three concrete, reproducible defects. **This is RQ4 — the strongest
      "Cedar was worth it" argument in the thesis, because the baseline has no analysis
      story at all.*
- [ ] **S5.8** Add a CI gate: editing a policy must not silently widen it.
      *Accept:* a PR that widens a policy fails CI with a counterexample.

**Sprint 5 exit:** RQ4 answered with named defects.

---

## Sprint 6 — Evaluation · Days 75–84 (Nov 17 – Nov 26)

- [ ] **S6.1** Get the benchmark datasets: RedCode-Exec and (if embodied is still in
      scope) SafeAgentBench. See `RUNNING.md` §7 for the expected paths.
      *Accept:* `code_agent.py` runs one index end to end.
      ⚠️ **Back up `expres/` first** — the authors' baseline results live there.
- [ ] **S6.2** Fix the cwd/import contradiction and the stray `break` at
      `src/code_agent.py:59` before drawing any conclusion from a run.
- [ ] **S6.3** **RQ2 — safety:** run RedCode-Exec + ToolEmu (144 cases) through
      unguarded / legacy AgentSpec / Cedar engine.
      *Accept:* unsafe-executions-prevented table for all three.
- [ ] **S6.4** **RQ2b — false positives.** Paired benign-task run for every safety number.
      *Accept:* no safety figure appears in the thesis without its utility twin.
      *(A guard that blocks everything scores 100% on RQ2. Don't hand the examiner that.)*
- [ ] **S6.5** **RQ5 — overhead:** finalise the latency numbers, sensors vs. decision.
      *Accept:* a chart. Expected finding: "the policy engine is free; detection is the cost."
- [ ] **S6.6** Consolidate every number into `docs/results.md`, one section per RQ.
- [ ] **S6.7** *(Optional, cut first if behind)* **Portability:** run the same `.cedar`
      file against a second binding — MCP tool calls via
      `cedar-policy-mcp-schema-generator`, or a Strands intervention.
      *Accept:* one page showing identical policies governing two frameworks.

**Sprint 6 exit:** every RQ has a number in `docs/results.md`.

---

## Sprint 7 — Write-up & artifact · Days 85–90 (Nov 27 – Dec 2)

- [ ] **S7.1** Assemble the thesis chapters per §G of the thesis plan. (Chapters 1–2 and
      Related Work should already be drafted — see the standing task below.)
- [ ] **S7.2** Reproducibility artifact: `README` for `agentguard/`, a Docker image, and a
      single `make reproduce` that regenerates every table in `docs/results.md`.
- [ ] **S7.3** Final pass on `docs/findings.md` — the defect list is the most quotable
      part of the work.
- [ ] **S7.4** Tag `v1.0-thesis` and open a PR from `dev-foued`.

---

## Standing tasks (do these continuously, not at the end)

- [ ] **W.1** Draft thesis Chapters 1, 2 (background) and 8 (related work) **during
      Sprints 0–2**, while the code is slow. Do not leave writing to Sprint 7.
- [x] **W.2** Keep `docs/findings.md` as a running lab notebook — every surprise,
      every bug, every counterexample, dated. Findings evaporate if not written down.
      Started 2026-09-06 at S2.3 with D-1…D-4. **Keep adding to it.**
- [ ] **W.3** After each sprint: update this file, commit, and push `dev-foued`.
- [ ] **W.4** After **every step**: run `make test`, then exercise the change in the
      bench (`make ui`). If a step adds behaviour the bench cannot show, extend the
      bench in the same commit — it is the primary way we look at this system.

---

## Risks to watch (from thesis plan §F)

| Watch for | Trigger to act | Action |
|---|---|---|
| Annotations unreadable from Python | S1.2 fails | Take the side-table fallback immediately; don't redesign |
| Java unavailable for ANTLR | S3.1 | Grammar work needs a JRE — install early or cut Sprint 3 |
| cvc5/symcc toolchain pain | S5.1 slips >3 days | Stay in Docker; if still stuck, reduce Sprint 5 to equivalence + shadowing only |
| Benchmark datasets unobtainable | S6.1 | Fall back to replaying `expres/*.jsonl` trajectories offline — enough for RQ1/RQ3/RQ4 |
| LLM API budget | S6.3 | Cache trajectories; most RQs run on replayed traces with zero API calls |
| Behind schedule at Day 46 | — | Cut Sprint 3 (hand-port 15 rules instead) and S6.7. **Never cut Sprints 4–5.** |

---

## Progress log

| Date | Step | Note |
|---|---|---|
| 2026-09-04 | S0.1–S0.7 | Forked repo set up; found and fixed the `Rule.triggered` crash on `AgentFinish` (any normal completion crashed with a tool-triggered rule loaded); smoke test green; corpus audit shows 21/42 shipped rules fail to parse under the repo's own grammar; the repo's own two tests both fail. |
| 2026-09-04 | S0.8 | Replaced `smoke_test.py` with a hermetic pytest suite: 25 tests, 17 pass + 8 strict-xfail. Tool execution is now a recording stub, so tests assert the tool was *reached* without running generated code. The 8 xfails are `strict=True`, so fixing the grammar in S3.1 will break them on XPASS and force an update in the same commit. Added a rule-order test documenting that AgentSpec's first-match-wins loop is order-dependent — the property Cedar removes (feeds S2.8). |
| 2026-09-04 | S0.8 | Added `tests/README.md` (how to run the suite and read its output) and an `AGENTSPEC_VERBOSE=1` trace mode. Found while documenting it: the `skip` path is **invisible** in LangChain's verbose trace — `_iter_next_step` yields its `AgentStep` without calling `run_manager.on_agent_action`, so a skipped action is never printed. Only `intermediate_steps` records it. Carry into the Cedar engine as a thing to fix, not copy. |
| 2026-09-04 | S0.8 | Added a `Makefile` (`make test` / `test-verbose` / `test-why` / `audit` / `venv`) after hitting `.venv/bin/pytest` path errors from the wrong cwd. Found a 9th grammar defect while verifying it: `ANY` is a **dead token** — declared at `AgentSpec.g4:9`, never referenced by the `event` parser rule at `:55`, so `trigger any` cannot parse, even though `Rule.triggered` implements the `any` wildcard at runtime. Now probe #9. |
| 2026-09-04 | S0.13 | Built the test bench (`make ui`): rule editor with live parse-checking, rule library, per-rule "why" panel, predicate prober, 8 worked examples, help page. Two findings while validating the examples. (1) A rule that fails to parse does **not** silently no-op — `Rule.from_text` accepts it with no error listener, then `RuleInterpreter` re-parses at *enforcement* time with one and raises `ValueError`, so a typo crashes the agent mid-run rather than at load. Worse than fail-open. (2) `enforce none` cannot demonstrate order dependence (it returns CONTINUE and never short-circuits); `skip` before `stop` gives SKIPPED and the reverse gives STOPPED. Both examples corrected and pinned by `tests/test_ui_examples.py`. Suite now 30 passed, 9 xfailed. |
| 2026-09-04 | S0.9 | `requirements-dev.txt` is now the single source of truth (Makefile + CI both read it). Trimmed the test-path dependencies: `FakeListLLM` lives in `langchain-core`, so `langchain-community` and `langchain-experimental` are no longer needed — a clean install drops from 69 packages to 43 and takes ~5s. CI has three jobs; every step was run locally in a throwaway venv before being written into the workflow. |
| 2026-09-04 | S0.9 | CI run #1 green on 3.11, 3.12 and 3.13 (~20s per job). The compat legs were pushed as `continue-on-error` because only 3.12 was verified locally; now that all three pass they are promoted to a single required matrix — a job that always passes but can never fail is not a signal. Actions turned out to be enabled on the fork already, so the "forks disable Actions" caveat did not bite. |
| 2026-09-05 | S0.10 | Audit tool now emits provenance (commit SHA, branch, date, Python/ANTLR versions, dirty flag) and repo-relative paths, so `docs/baseline-audit.md` is citable rather than just a table of numbers. `make audit-freeze` regenerates it. |
| 2026-09-05 | S0.11 | Profiler landed. **77.6% of AgentSpec's guard cost is re-parsing rule text** (0.135 ms/step), against 18.4% evaluating predicates and 4.0% enforcement — because `verify_and_enforce` re-lexes and re-parses every triggered rule's raw text on every single action. Pure waste: the rules never change between steps. This is the strongest RQ5 result available before Cedar exists, and it is an argument for the *architecture*, not just the language. |
| 2026-09-05 | S0.12 | Expected one fail-open mode; found four. (1) **Silent acceptance** — a bad rule loads and then raises `ValueError` mid-run. (2) **Silent truncation** — `trigger Gmail.SendMail` loads as event `Gmail`, so the rule arms on a *different tool than written*: the most dangerous of the four, since it fails silently and permanently. (3) **Internal crash** — a *two-token* comment (`// index 0`) breaks ANTLR recovery hard enough that `Rule.from_text` dies with `AttributeError: 'RuleParser' object has no attribute 'event'`, while a *one-token* comment (`//index1`) is accepted; identical-looking comments behave differently by word count. (4) **Unregistered predicates** — 17 of the names used by `pythonrepl.ar` are defined in Python but never added to `predicate_table`, including `is_malware`, the corpus's very first rule. Checked whether the grammar's 36 predicates and the registry had diverged: they have not, and that is now a test. |
| 2026-09-05 | S1.1 | Cedar reaches Allow and Deny in AgentSpec's own PARC shape. Confirms M1 concretely: `destuctive_os_inst` cannot run inside a policy (Cedar is pure and total), so it runs in Python and arrives as `context.flags` — detection in Python, decision in Cedar. |
| 2026-09-05 | S1.2 | **Unblocked, but not the way the plan assumed.** `diagnostics.id_annotations_by_reason` carries only `@id` — the name is accurate and the plan misread it. `policies_to_json_str()` carries every annotation, keyed by the same `policy0/1/2` ids `diagnostics.reasons` returns, so the side-table joins directly and is built by cedarpy's own Cedar parser rather than a regex. None of the three fallbacks the plan listed are needed. Second finding: **Cedar does not return determining policies in source order** — for a two-forbid decision it returned `['policy2','policy1']`. Anything reading "the first determining policy" would be reading an unspecified ordering; the lattice join makes it irrelevant by construction. That is the concrete mechanism behind M2, and it hands S2.8 its property to test. |
| 2026-09-05 | S1.3 | Validation catches typo'd context and entity attributes, type mismatches, unknown entity types and unknown actions — all at load, none of which AgentSpec can detect at all. Unplanned bonus: the spike **answers S2.2 five weeks early**. The same misspelled flag is missed under `flags: Set<String>` (any string is a valid member, so the policy type-checks and silently never fires) and caught under `flags: { name: Bool, ... }`. A silently-never-firing safety rule is the exact failure mode S0.12 documented, so the record-of-`Bool` codegen is now evidence-backed rather than a preference. |
| 2026-09-05 | S1.4 | 0.0579 ms mean / 0.0772 ms p99 per decision with a pre-parsed `PolicySet`. Passing policy text instead costs 2× — worth knowing before writing the engine, since it is the same mistake AgentSpec makes. Against S0.11: a whole Cedar decision is cheaper than AgentSpec's *parsing phase alone*, and 3.3× cheaper than its whole guard path, while evaluating three policies with schema validation and an order-independent result. RQ5's honest headline is still "the engine is free, detection is the cost" — this is a ratio, not a latency problem. |
| 2026-09-05 | S1.5 | First real schema landed, namespaced `AgentGuard` per thesis §C.2 — the spikes were namespace-free, and paying that cost now beats rewriting the corpus at S3.4. Kept strictly smaller than §C.2 with each omission annotated by the step that adds it, so the file records what is *deferred* rather than pretending to be finished. Added `tools/validate_policies.py` as the executable form of the S2.5 requirement ("refuse to start on failure") — it exits non-zero, so it doubles as a CI gate. One find while writing the tests: the schema also rejects an **unnamespaced** `Action::"invoke"`, so the namespace cannot be half-adopted by accident. Left the `flags: Set<String>` hole open deliberately and pinned it with a test that must break at S2.2. |
| 2026-09-05 | env | The Windows checkout could not run the suite at all: `.venv` was the upstream environment (LangChain 1.4, Python 3.14) and LangChain 0.3.x cannot import under 3.14 — `Chain.dict()` shadows `dict` when PEP 649 evaluates `Optional[dict[str, Any]]`, so `langchain.chains.base` fails at class creation. Rebuilt `.venv` on 3.12.14 from `requirements-dev.txt`. One genuine portability bug surfaced: `test_rule_writes_are_confined_to_the_library` compared a native path against a `/`-separated literal. Fixed; suite green on Windows. |
| 2026-09-05 | S1.6 | Two policies, and a finding that came out of writing the `@source` annotation honestly. The walking skeleton's rule (stop on `destuctive_os_inst`) is **not** in the shipped corpus: the nearest match, `pythonrepl.ar#index8`, also requires `involve_system_file` and only asks the user. That is the norm — **24 of the 26 rules in `pythonrepl.ar` enforce `user_inspection`**, and of the two that `stop`, one is `is_malware`, whose predicate is never registered (S0.12). The shipped PythonREPL corpus has exactly **one working hard stop**. Second: Cedar validates policy logic but treats annotations as opaque strings, so `@advice("stopp")` type-checks and then crashes the resolver at decision time — the same silent-failure shape as AgentSpec's. Added an annotation lint to `tools/validate_policies.py`; the lattice moves to `agentguard/advice.py` at S2.4. |
| 2026-09-05 | S1.7 | Cedar decides, end to end. Two findings, both about failing **closed**. (1) When Cedar cannot evaluate a request it returns `Decision.NoDecision` and puts the cause in `diagnostics.errors` — it does not raise. A malformed entity store does exactly this. Any engine that reads "not Deny" as permission turns an internal fault into a **silent allow**, which is the failure mode this project exists to remove; `decide()` treats NoDecision-or-errors as `stop`. (2) The tool name reaches the request from the model's own output, so it is attacker-influenced whenever the task prompt is. Interpolated raw into `Tool::"..."` a crafted name closes the uid early — verified: it yields `failed to parse schema from request`, so unescaped it is a denial of service rather than a bypass, but only because of finding (1). Escaped at the boundary anyway; a parser is not an access control. Also worth recording: under Cedar the policy set comes from `policies/`, not from the `rules=` argument, so `test_no_rules_means_no_interference` legitimately changes meaning — S2.7 has to decide what "no rules" means for an engine whose policies are ambient. |
| 2026-09-05 | S1.8 | Panel wired, and it immediately earned its keep: **example 3 disagrees**. "No rules loaded" is AgentSpec's control case — an empty rule list means nothing can fire — but AgentGuard's policy set is *ambient*, loaded from `policies/` rather than passed in, so the same call is denied. Neither engine is wrong; the two have different notions of where policy lives, and S2.7 has to pick one deliberately. **Example 7** is the other one worth looking at: a rule that does not parse takes the AgentSpec run down mid-flight (verdict ERROR) while Cedar still returns a decision — RQ6 visible in the UI rather than argued in prose. Panel is a decision, not a second agent run; the engine toggle and the verdict diff stay with S2.10. |
| 2026-09-06 | S2.1 | Registry landed, and the metadata is derived rather than declared — `reads` from the AST, `domain` from the defining module, `cost` from `reads` — so S2.2 can generate the schema without a hand-maintained table in the middle of it. Three findings. (1) **The plan's third domain is empty.** `rules/manual/toolemu.py` is a 0-byte file and `terminal.py` keeps its four predicates in a private `table` dict `table.py` never merges, so the registry is 25 code + 11 embodied and *zero* toolemu. `src/rules/__pycache__/` still holds **38 orphaned `.pyc` files** with no `.py` source — `tool_emu_predicate_table` and 30+ per-toolkit predicate modules — so that layer was deleted upstream and survives only as bytecode. S3.4 and S6.3 both assume it exists. (2) **Domain is not decoration:** run an embodied sensor on a code agent's trace and it *raises* rather than returning False — 5 of 11 do — and the exception class is not even stable (`is_unsafe_fillliquid` gives AttributeError on an input with spaces, IndexError without). So "catch the known exception" is not available to S2.3; only not running the sensor is. Every raising sensor is one whose `reads` include `intermediate_steps`, so the metadata is sufficient to avoid them — that is a test. (3) **35 of 36 predicates never look at the user's task.** Only `predicate11` reads `user_input`, and its name is a placeholder. A guard that cannot relate the action to the request cannot distinguish the deletion that was asked for from the one that was not — relevant to RQ2b, since it bounds how few false positives the baseline can possibly achieve. |
| 2026-09-06 | S2.2 | Schema is generated from the registry, and `make validate` fails when the file on disk no longer matches it — a hand-edited schema type-checks perfectly and silently drops a flag, which is a policy that can never fire, so the staleness check is the point rather than tidiness. **The plan's record-of-Bools has a sub-variant it did not name, and only one of the two is honest.** With *required* attributes Cedar answers `NoDecision` unless the request carries every declared flag — so shipping them would mean sending `false` for the 35 sensors that never ran, asserting "the dangerous thing is not happening" about checks nobody performed. That is the exact fail-open shape this project exists to remove. With *optional* attributes the request carries only what was evaluated, and Cedar **refuses to validate an unguarded access** (`unable to guarantee safety of access`) — so a policy is forced to write `context.flags has X && context.flags.X` and the three states stay distinct: fired / ran-and-said-no / never-ran. The verbosity is the honesty, and it is mechanical, so S3.3's compiler emits it. `run_sensors` now returns a map rather than a list of names for the same reason. S1.5's deliberately-failing test has flipped: a misspelled flag is now rejected by name at load. Bench shows `destuctive_os_inst = false` as a distinct muted pill, so "ran and said no" is visible rather than inferred. |
| 2026-09-06 | S2.3 | Materialisation extracted, and selecting sensors **by domain** rather than by name turned out to be the whole step. Running all 25 code sensors instead of one immediately produced **three corpus defects**, now written up in `docs/findings.md`. **D-1: `is_buggy_ip_validation_code` is a constant `True` in practice** — it asks whether the *code text* starts with a literal `^` and ends with `$`, which almost nothing does, so it short-circuits to True on every input we could construct including the empty string and a *correct* IP-validation regex. Any rule using it fires always; at `user_inspection` (24 of 26 rules) that prompts the user on every call, which is how a guardrail gets switched off. **D-2: `write_to_io` matches `print\(.*?\)`**, so `print(6 * 7)` — the bench's own benign example — is "writing to I/O". Two of 25 sensors fire on trivial arithmetic; one fires on the empty string. **D-3: the `.ar` corpus and the executable `checks{}` table disagree at 8 of 16 indices**, and six names on the `.ar` side are not registered at all, so those rules cannot execute — the same class as S0.12's `is_malware` but systematic, and a hard bound on what S3.4 can compile faithfully. **D-4 corrects an S2.1 claim of mine**: I said 35 of 36 predicates ignore the user's task; it is 36 of 36 — `predicate11` only *forwards* `user_input` to helpers that ignore it, so "references the name" overstated it. Also measured: sensor cost is dominated by input size, not sensor count (25 sensors on 2 KB = 2.98 ms vs a 0.058 ms Cedar decision, so detection is ~51× the decision) — the concrete form of RQ5's headline. |
| 2026-09-06 | S2.4 | Lattice, join and substitution rule now have one home, and the duplicate in `tools/` is gone. The join is a meet on a total order, so it is idempotent, commutative and associative — that is what makes the outcome independent of the order Cedar lists determining policies in, and Cedar obliged again during testing by returning `['policy1','policy0']` for a two-forbid decision while the resolution stayed `user_inspection`. **D-5: substitution is unreachable in the baseline**, in four compounding ways — the grammar parses `invoke_action(t,{...})`, `enterEnforcement` then looks up the whole *source text* in `ENFORCEMENT_TO_CLASS` and raises KeyError mid-run, `InvokeAction` is never registered so it could not be selected anyway, and it is a no-op returning the original action even if it were. No corpus rule uses it, which is presumably why nobody noticed. Consequence for the write-up: substitution is a capability we add, not a baseline we beat. Kept it off the lattice for the reason the plan asked us to state: a rewrite *invokes a tool*, so it can be more dangerous than what it replaced and has no honest rank between `skip` and `stop`. Falling back to the join of the *other* policies would discard the rewrite the author asked for and make the outcome depend on which others happened to fire — the composition sensitivity the lattice exists to remove — so a non-unique substitution resolves to `stop`. |
| 2026-09-06 | S2.5 | Engine split out; `executor.py` is now only the LangChain binding. **RQ6 answered, and one of my own earlier claims corrected.** S2.2 said a misspelled flag is now rejected at load. It is not — `has` is well typed for *any* attribute name, so `context.flags has destuctive_os_inzt && context.flags.destuctive_os_inzt` validates cleanly and the policy silently never fires. And the guarded form is the **only** one Cedar accepts for an optional attribute, so **the idiom S2.2 mandates is exactly the one that defeats the check S2.2 added**: two individually-correct features composing into a hole. What closes it is the engine's **coverage check** — every flag a policy reads must be one the configured domain's sensors will materialise — which Cedar cannot do, because the schema legitimately declares all 36 sensors and only the engine knows which subset it runs. That check also catches the other direction (an embodied flag in a code-domain engine) and is the direct analogue of S0.12's `is_malware`. On the acceptance criterion: the S0.12 xfails **cannot** flip without patching `src/rule.py`, which would make every later comparison a comparison against a repaired baseline; kept them red as the record and answered RQ6 in `tests/test_fail_closed.py`, four modes mapped one-to-one. Also noted for S2.7: AgentGuard refuses to start with no policies at all (an engine with none allows everything), where AgentSpec starts happily with an empty rule list — the same where-does-policy-live disagreement as bench example 3. |
| 2026-09-06 | S2.6 | Mapping done by reuse — the five lattice outcomes go through AgentSpec's own unmodified classes — but writing the tests turned up **D-6: `llm_self_reflect` crashes the run**. `LLMSelfReflect.apply` returns the raw LangChain object `agent.plan()` gave it, not an AgentSpec `Action`; the executor feeds that straight back into its own loop and dies on `action.is_finish()`. Verified end to end through the bench: `AttributeError: 'AgentFinish' object has no attribute 'is_finish'`. So with D-5, **two of the six enforcement forms the grammar accepts do not work** — leaving `stop`, `skip`, `user_inspection`, `none`. We wrap the return value rather than copy the bug, which is the only reason the outcome exists on our side; the write-up must call that "made to work", not "more expressive". **D-7** counts the enforcement side of the corpus: of 61 `enforce` clauses, 40 use one of the two working outcomes; 18 are apollo `config` assignments whose *checks* already fail with `unsupported type` before enforcement is reached (a family the interpreter never supported, not a regression), 1 is `llm_self_examine` which is not a grammar token at all, and 1 is a parameterised `user_inspection("...")` which does not parse. Design point worth keeping: a substitution is **re-guarded**, because it replaces a call the policy set just judged with one the policy author wrote — unguarded, `@substitute_tool` would be a documented bypass. Bounded at 3 redirects so two policies pointing at each other cannot loop. |
| 2026-09-06 | S2.7 | Parity, with the criterion read honestly rather than literally. `make test-cedar`: **417 passed, 15 skipped, 0 failed** — every skip carries its reason and `-rs` prints them. All 15 have an AgentSpec *rule* as their subject: most are blocked on S3.3 (until a rule can become a policy the Cedar engine has nothing to decide on), and **two can never pass by design** — `test_first_matching_rule_decides` and `test_order_dependence_is_real` assert that swapping two rules flips the verdict, which is exactly the property the lattice removes. A literal "every test passes under both" would have required either deleting those or making Cedar order-dependent; both are worse than a documented skip. **Settled the where-does-policy-live question** that surfaced at S1.8, S2.5 and S1.7: policy is **ambient**, read from `$AGENTGUARD_POLICIES`, because a guard whose rule set arrives as a constructor argument is opt-in per construction site — the code being guarded can construct itself unguarded. That is a design claim, not a measurement, and it is labelled as one. It also has a cost: "run with these rules" has no direct equivalent, so `test_no_rules_means_no_interference` needed a translation (baseline-permit-only policy set) rather than a comparison — and now passes on **both** engines, which is the question in executable form. |
