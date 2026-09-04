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

**Current position:** Sprint 0, Step S0.5.

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
      *Accept:* `.venv/bin/python smoke_test.py` ends with `SMOKE TEST: PASS`.
- [x] **S0.6** Write `tools/audit_rules.py` — parse audit of the shipped rule corpus. ✅ 2026-09-04
      *Accept:* `.venv/bin/python tools/audit_rules.py src` emits the three Markdown tables.
- [x] **S0.7** Write `RUNNING.md` — setup, testing, known breakages. ✅ 2026-09-04
- [ ] **S0.8** Convert `smoke_test.py` into a real pytest suite at `tests/`.
      Split into `tests/test_enforcement.py` (scenarios A/B + one per enforcement mode:
      `stop`, `skip`, `none`) and `tests/test_rule_parsing.py` (the B.2 feature probes as
      xfail-marked tests documenting current grammar limits).
      *Accept:* `.venv/bin/pytest -q` is green; ≥8 tests collected.
- [ ] **S0.9** Add `requirements-dev.txt` (pytest, the pinned runtime deps) and a
      GitHub Actions workflow `.github/workflows/ci.yml` running `pytest` on push.
      *Accept:* workflow file committed; `act` or a pushed run is green.
- [ ] **S0.10** Commit the audit output to `docs/baseline-audit.md` (generated, dated).
      This is the thesis's Chapter 3 evidence — freeze it now, before we change anything.
      *Accept:* file exists with the tables and the exact commit SHA it was generated from.
- [ ] **S0.11** Add latency instrumentation to `ControlledAgentExecutor._iter_next_step`:
      time (LLM plan | rule parse | predicate eval | enforcement) per step, written as
      JSONL to `expres/latency/baseline.jsonl` behind an env flag `AGENTSPEC_PROFILE=1`.
      *Accept:* a smoke-test run produces a JSONL file with 4 timings per step.
- [ ] **S0.12** Record the fail-open behaviour (B.3) as a failing/xfail test:
      a malformed rule must be *rejected*, and currently isn't.
      *Accept:* `tests/test_fail_open.py::test_malformed_rule_is_rejected` xfails with a
      clear message. This test turns green in Sprint 2 — it's our headline RQ6 result.

**Sprint 0 exit:** green pytest suite, CI running, baseline audit + latency frozen in `docs/`.

---

## Sprint 1 — Cedar spike & walking skeleton · Days 8–16 (Sep 11 – Sep 19)

Goal: the smallest possible end-to-end path where **Cedar** makes the decision.
Resolve every unknown here, before writing real code.

- [ ] **S1.1** `pip install cedarpy`; write `spikes/hello_cedar.py` that authorizes a
      hard-coded request against a hard-coded policy.
      *Accept:* prints `Allow` for one request and `Deny` for another.
- [ ] **S1.2** ⚠️ **Spike the annotation question.** Can we read an arbitrary `@advice("...")`
      annotation off the policies named in `diagnostics.reasons` from Python?
      Try `diagnostics.id_annotations_by_reason` first.
      *Accept:* `spikes/annotations.py` prints the advice string for a denying policy —
      **or** documents in `docs/spikes.md` that it can't, and which fallback we take
      (side-table parsed at load time / Cedar CLI JSON / PyO3 wrapper).
      *This blocks the whole advice design. Do it on day one of the sprint.*
- [ ] **S1.3** Spike schema validation: write a deliberately broken policy (typo'd
      attribute) and confirm `validate_policies()` catches it.
      *Accept:* `spikes/validation.py` prints the validation error.
- [ ] **S1.4** Measure Cedar decision latency: 10k `is_authorized` calls, report mean/p99.
      *Accept:* number recorded in `docs/spikes.md`. (Expect microseconds — this becomes RQ5.)
- [ ] **S1.5** Write the first real schema `policies/schema.cedarschema` — just `Agent`,
      `Tool`, `action invoke`, and a `context` with `flags: Set<String>`.
      *Accept:* `validate_policies()` passes against a hand-written policy.
- [ ] **S1.6** Write `policies/core.cedar` with two policies: a baseline `permit`, and a
      `forbid` for `destuctive_os_inst` carrying `@advice("stop")`.
- [ ] **S1.7** Wire it in: `agentguard/executor.py` with `CedarControlledAgentExecutor`,
      one hard-coded sensor (`destuctive_os_inst`), behind an env flag `AGENTGUARD=cedar`.
      *Accept:* `smoke_test.py` passes **both** scenarios with `AGENTGUARD=cedar` set,
      producing the same verdicts as the original engine.

**Sprint 1 exit:** the same smoke test passes through either engine. Screenshot it —
it goes in the thesis.

---

## Sprint 2 — The engine · Days 17–34 (Sep 20 – Oct 7)

Goal: a real, tested `agentguard/` package. No hard-coding left.

- [ ] **S2.1** `agentguard/sensors.py` — a registry wrapping all 36 predicates from
      `rules.manual.table.predicate_table`, each with metadata: name, domain
      (code/embodied/toolemu), cost hint, which flags it can set.
      *Accept:* `len(SENSORS) == 36`; `pytest tests/test_sensors.py` green.
- [ ] **S2.2** `agentguard/schema.py` — generate `schema.cedarschema` **from** the sensor
      registry, so flags are a validated record-of-bools rather than free strings.
      Keep the `Set<String>` variant behind a flag so we can compare both (thesis §C.2).
      *Accept:* regenerating the schema after adding a sensor requires no hand-editing.
- [ ] **S2.3** `agentguard/request.py` — materialisation: `RuleState → (Request, Entities)`.
      Runs sensors, builds principal/action/resource/context.
      *Accept:* golden-file test: a fixed `RuleState` produces a fixed JSON request.
- [ ] **S2.4** `agentguard/advice.py` — the advice lattice
      (`stop > user_inspection > llm_self_reflect > skip > allow`), plus the rule that
      `substitute` only applies when it is the unique determining policy.
      *Accept:* `pytest tests/test_advice.py` covers every pair in the lattice.
- [ ] **S2.5** `agentguard/engine.py` — load policies, **validate against the schema at
      startup and refuse to start on failure**, evaluate, resolve advice.
      *Accept:* **S0.12's xfail test now passes.** Flip it from xfail to a real assertion.
      This is RQ6 — write the result down the day it goes green.
- [ ] **S2.6** `agentguard/enforcer.py` — map advice onto the existing `enforcement.py`
      classes (reuse them; don't rewrite).
      *Accept:* one test per enforcement mode, all green.
- [ ] **S2.7** Finish `agentguard/executor.py` — no hard-coding, feature-flag parity.
      *Accept:* every test in `tests/` passes under both `AGENTGUARD=legacy` and `=cedar`.
- [ ] **S2.8** Property test: **order independence.** Shuffle the policy set 100× and
      assert the verdict never changes. Then do the same with AgentSpec's rule list and
      show that it *does* change.
      *Accept:* `tests/test_order_independence.py` green for Cedar, and a documented
      counterexample for the legacy engine in `docs/findings.md`.
      *(This is a free, high-value thesis result. Don't skip it.)*
- [ ] **S2.9** Re-run the latency instrumentation with the Cedar engine.
      *Accept:* `expres/latency/cedar.jsonl`; sensors vs. decision split recorded.

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
- [ ] **W.2** Keep `docs/findings.md` as a running lab notebook — every surprise,
      every bug, every counterexample, dated. Findings evaporate if not written down.
- [ ] **W.3** After each sprint: update this file, commit, and push `dev-foued`.

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
