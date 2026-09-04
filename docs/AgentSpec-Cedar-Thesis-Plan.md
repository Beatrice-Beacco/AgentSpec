# Putting Cedar inside AgentSpec
### A thesis plan: replacing an ad-hoc safety DSL with a formally-analysable policy engine

**Prepared:** 3 September 2026
**Target repo:** <https://github.com/haoyuwang99/AgentSpec> (`e6fa390`, LangChain-migrated `main`)
**Target paper:** Wang, Poskitt & Sun, *AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents*, ICSE 2026 — [arXiv:2503.18666](https://arxiv.org/abs/2503.18666)
**Policy engine:** [Cedar](https://www.cedarpolicy.com/) 4.12.0 (Rust, Jul 2026) · `cedarpy` 4.8.7 (Python) · `cedar-policy-symcc` (SMT verification)

---

## 0. TL;DR — what this thesis actually is

> AgentSpec is a **runtime monitor** for LLM agents: it sits inside the agent's think→act loop, and before every tool call it asks "does any safety rule fire, and if so what do we do about it?" Its rules are written in a small hand-rolled DSL (`trigger / check / enforce`).
>
> Cedar is a **formally specified, machine-verified authorization language** (default-deny, order-independent, guaranteed-terminating, with an SMT-based analyser).
>
> **The thesis: rip out AgentSpec's ad-hoc rule language and put Cedar in its place — without losing the two things Cedar cannot do on its own** (arbitrary Python predicates over agent code/trajectory, and richer-than-allow/deny enforcement). The result is a policy engine for agent safety whose rule sets you can *validate, verify, compare and prove things about* — which the original cannot.

The intellectual meat is in the **impedance mismatch**, not the plumbing. Three mismatches, three contributions:

| # | Mismatch | Contribution |
|---|---|---|
| M1 | Cedar expressions are **pure and total** — no regex, no AST walking, no `psutil`. AgentSpec predicates are arbitrary Python over generated code. | An **attribute-materialisation layer**: predicates become *sensors* that produce a typed, schema-validated Cedar context. Policy logic and detection logic get cleanly separated. |
| M2 | Cedar decides **Allow/Deny**. AgentSpec has five outcomes (`stop`, `skip`, `user_inspection`, `llm_self_reflect`, `invoke_action`). | An **obligation/advice layer** on top of Cedar annotations, with a defined precedence lattice so multiple firing policies compose deterministically. |
| M3 | Cedar is **stateless per request**; "harmful *execution path*" is a property of the whole trajectory. | A **Session entity carrying taint state**, turning stateless authorization into a stateful runtime monitor. This is where the "detects harmful execution paths" phrasing gets its teeth. |

Everything else in this document is how to build and evaluate that.

---

# PART A — What the pieces are

## A.1 AgentSpec, concretely

AgentSpec is a **domain-specific language + runtime enforcement framework** for LLM agents. Not a model, not a filter on prompts — a *supervisor around the agent loop*.

### The rule language

```
rule @manipulate_system_file      // rule name
trigger
    PythonREPL                    // which tool/event arms the rule
check
    involve_system_file           // predicates (implicit AND)
    copy_file
enforce
    user_inspection               // what to do when they all hold
end
```

Three clauses, and that is the whole language:

- **`trigger`** — an event. Either a tool name (`PythonREPL`, `TodoistDeleteTask`), a lifecycle event (`before_action`, `after_action`, `state_change`, `finish`), or `any`.
- **`check`** — a conjunction of named predicates. Each name maps to a **Python function** with the fixed signature `f(user_input, tool_input, intermediate_steps) -> bool`.
- **`enforce`** — one of `stop`, `skip`, `user_inspection`, `llm_self_reflect`, `invoke_action(tool, {...})`, `none`.

### How it hooks into the agent

The whole framework is ~1,300 lines of Python. The load-bearing parts:

| File | Role |
|---|---|
| `src/spec_lang/AgentSpec.g4` | ANTLR4 grammar (~60 lines). Generates lexer/parser/listener. |
| `src/rule.py` | `Rule.from_text()` — parses a rule, extracts `id` + `event`, keeps raw text. |
| `src/interpreter.py` | `RuleInterpreter.verify_and_enforce()` — **re-parses the rule text on every action**, walks the tree, evaluates predicates via `predicate_table`, dispatches to an enforcement class. |
| `src/enforcement.py` | The five enforcement strategies as classes returning `(EnforceResult, Action)`. |
| `src/controlled_agent_excector.py` | `ControlledAgentExecutor(AgentExecutor)` — overrides LangChain's `_iter_next_step` so that between "LLM planned an action" and "tool actually runs", `validate_and_enforce()` gets a veto. **This is the interception point.** |
| `src/state.py` | `RuleState` — the monitor's view: action, agent, `intermediate_steps`, `user_input`, reflection depth. |
| `src/rules/manual/*.py` | The predicate implementations (632 lines for Python-REPL risks, 354 for embodied). |
| `src/rules/manual/*.ar` | The shipped rule corpora. |

The control flow that matters, from `controlled_agent_excector.py:_iter_next_step`:

```
LLM plans  →  Action.from_langchain(output)
           →  build RuleState(action, agent, intermediate_steps, user_input)
           →  validate_and_enforce(action, state)
                 for each rule:
                     if rule.triggered(action.name, action.input):
                         RuleInterpreter(rule, state).verify_and_enforce(action)
                         → CONTINUE / SKIP / STOP / SELF_REFLECT
           →  tool actually executes (or doesn't)
```

### The three evaluation domains

1. **Code agents** — LangChain agent with `PythonREPL`; benchmark **RedCode-Exec** (27 risky-scenario indices × 30 generated programs). Results in `expres/code/python/`.
2. **Embodied agents** — AI2-THOR household robot; benchmark **SafeAgentBench**. Rules like "don't put a fork in the toaster", "don't microwave metal". Results in `expres/embodied/`.
3. **Autonomous vehicles** — Baidu **Apollo** via the uDrive instrumentation; rules in `src/rules/apollo/` are *translated* into runtime planner-parameter overrides rather than vetoes (`src/translator.py`).

Plus **ToolEmu** (144 cases, 38 toolkits, in `benchmarks/ToolEmu/`) for LM-emulated tool agents.

### Reported results (the numbers to beat / preserve)

- Code agents: **>90 %** of unsafe executions prevented
- Embodied: **all** hazardous actions eliminated
- AV: **100 %** compliance in the tested scenarios
- Overhead: **millisecond-level**
- LLM-generated rules (o1): 95.56 % precision / 70.96 % recall (embodied); 87.26 % of risky code identified

---

## A.2 Cedar, concretely

Cedar is AWS's open-source authorization policy language. It answers exactly one question — *"is this principal allowed to do this action on this resource in this context?"* — and answers it with strong guarantees.

### The PARC model

Every decision is a request `(principal, action, resource, context)` evaluated against a **policy set** and an **entity store**.

```cedar
permit (
  principal == User::"alice",
  action    == Action::"read",
  resource  in Folder::"reports"
)
when { context.mfa_authenticated };
```

### Why anyone would pick it for agent safety

| Property | Why it matters here |
|---|---|
| **Default deny** | Nothing is allowed unless a `permit` matches. Fail-closed by construction. |
| **`forbid` beats `permit`, always** | A safety rule can never be shadowed by a permissive one. |
| **Order-independent** | The decision doesn't depend on the order rules were loaded. Contrast with AgentSpec's first-match-wins loop. |
| **Total & terminating** | No loops, no recursion, no side effects. O(n) evaluation. A malicious/buggy policy cannot hang the agent. |
| **Schema + validation** | `validate_policies()` catches typos, type errors, attribute-not-in-schema *before deployment*. |
| **Machine-checked semantics** | The evaluator is modelled in Lean (`cedar-spec`) and differentially tested. |
| **SMT-based analysis** (`cedar-policy-symcc` + cvc5) | Prove *properties of a rule set*: never-errors, always-denies, subsumption, **equivalence**, disjointness — with counterexamples. |
| **Annotations** | `@id(...)`, `@advice(...)` — arbitrary key/value metadata carried on policies, ignored by evaluation, readable by the host application. **This is the hook for enforcement modes.** |
| **Readable** | Policies read like structured English; a safety engineer who doesn't write Python can audit them. |

### What Cedar deliberately cannot do

This list *is* the design constraint. Internalise it before writing a line of code.

- ❌ No regular expressions (only `like` with `*` wildcards)
- ❌ No user-defined functions; extension functions are a **fixed** set (`ip`, `decimal`, `datetime`/`duration`)
- ❌ No parsing, no AST inspection, no I/O, no calling out to Python
- ❌ No loops or unbounded iteration (set ops are bounded)
- ❌ No mutation — evaluating a policy cannot change state
- ❌ Only two outcomes: `Allow` or `Deny`

So `is_destructive(code)` — a regex sweep over LLM-generated Python — **can never live inside a Cedar policy**. It has to run *before* the request is built. That is M1, and it dictates the architecture.

### Prior art you must cite and differentiate from

Cedar-for-agents is no longer a blank field. Be explicit about where you sit:

- **Amazon Bedrock AgentCore Policy** — uses Cedar to authorize MCP tool calls at a gateway. Principal = agent/user, Action = tool, Resource = gateway, **Context = the tool arguments the LLM produced**.
- **Strands Agents `CedarAuthorization` intervention** — Cedar at the tool-call boundary in an agent SDK; fail-closed, deny feeds back to the agent.
- **`cedar-policy/cedar-for-agents`** — generates Cedar schemas automatically from MCP tool descriptions (Rust/WASM/Python).
- **AutoCedar** — verifier-guided LLM synthesis of Cedar policies.

**Your differentiation, in one sentence:** *all of the above authorize a single tool call from its arguments; none of them reason over the agent's execution trajectory, and none of them support enforcement outcomes richer than allow/deny.* M2 and M3 are the gap.

---

# PART B — The gap (with evidence)

Don't just assert that AgentSpec's DSL is ad hoc. **Measure it.** I ran every shipped rule file through AgentSpec's own generated ANTLR parser. Reproduce this on day one — it is a chapter's worth of motivation.

## B.1 The shipped rule corpus does not parse under its own grammar

Whole-file parse, using the repo's `AgentSpecLexer`/`AgentSpecParser`:

| Rule file | Result |
|---|---|
| `src/rules/manual/pythonrepl.ar` | **99 syntax errors** |
| `src/rules/manual/toolemu.ar` | **44 syntax errors** |
| `src/rules/manual/embodied.ar` | **9 syntax errors** |
| `src/rules/apollo/S1–S3, S5–S7.rule` | 1–3 errors each (`&` is not in the grammar) |
| `src/rules/apollo/S4, S8, S9.rule` | OK |
| `src/rules/manual/terminal.ar`, `apollo/plan/s1.ar` | empty files |

Stripping comments and parsing rule-by-rule:

| File | Rules | Parse OK | Parse FAIL |
|---|---:|---:|---:|
| `pythonrepl.ar` | 26 | 10 | **16** |
| `toolemu.ar` | 11 | 0 | **11** |
| `embodied.ar` | 5 | 2 | **3** |

## B.2 Which language features are missing — probe results

| Construct (as used in the repo/README) | Parses? |
|---|---|
| `// comment` | ❌ no comment token in the grammar at all |
| Predicate not in the hard-coded token list (e.g. `is_malware`) | ❌ |
| `check True` (capitalised, as in `toolemu.ar`) | ❌ — only lowercase `true` |
| `trigger Gmail.SendMail` (dotted, as in `toolemu.ar`) | ❌ |
| `trigger A \| B` (alternation, as in `toolemu.ar`) | ❌ |
| `trigger turn on` (multi-word, as in `embodied.ar`) | ❌ |
| `enforce llm_self_examine` (**the README's own name**) | ❌ — grammar says `llm_self_reflect` |
| `check p & q` (as in `apollo/*.rule`) | ❌ |
| `!predicate`, `invoke_action(t, {"k":"v"})`, lowercase `true` | ✅ |

**The root cause is architectural:** the predicate vocabulary is a *literal token in the grammar* —

```antlr
PREDICATE: 'involve_system_file' | 'submit_post_request' | ... ;   // 36 alternatives
```

— so **adding one predicate requires regenerating the parser** (the README says so explicitly: "Extend the grammar… run ANTLR"). A safety DSL where users cannot add a check without a build step is not extensible, and `gen.py` exists purely to rewrite the `.g4` file programmatically. That is the smell.

## B.3 It fails *open*, not closed

`Rule.from_text()` installs no error listener. Malformed rules print to the console and **return a valid-looking `Rule` object**:

```
$ python from_text_probe.py
line 6:0 mismatched input 'enforce' expecting '('
### unlisted predicate (is_malware)
  RESULT: constructed -> {'id': 'is_malware', 'event': 'PythonREPL'}
```

Then in `interpreter.py`, `self.check` is initialised to `True` and only narrowed by `enterCheckClause` — which never fires if the check clause didn't parse. A broken safety rule therefore either **silently permits** or crashes with an `AttributeError` on `self.enforce`. Neither is acceptable for a safety mechanism.

Cedar's default-deny + `validate_policies()` against a schema fixes precisely this class of bug. **Make this an explicit research claim, and quantify it.**

## B.4 The rest of the gap

| Weakness | Consequence | Cedar's answer |
|---|---|---|
| No formal semantics for the rule language | Cannot prove anything about a rule set | Lean-modelled semantics |
| Rules evaluated **in list order**, first non-CONTINUE wins (`validate_and_enforce`) | Adding a rule can silently change behaviour of existing ones | Order-independent; `forbid` always wins |
| No conflict / redundancy / subsumption detection | Rule sets rot as they grow | `symcc`: equivalence, subsumption, disjointness — with counterexamples |
| No schema — predicates are free-floating Python | Typos = silent no-ops | Schema-validated entities, actions, context |
| `check` is a bare conjunction | No `OR`, no comparisons, no quantifiers | Full boolean + `if/then/else`, `in`, `has`, `like`, set ops |
| `Rule.triggered()` uses `startswith` substring matching on tool input | Both over- and under-triggers | Typed action + entity hierarchy |
| Rule text is **re-lexed and re-parsed on every single agent step** | Avoidable per-action latency | Parse once into a `PolicySet`; evaluate in µs |

---

# PART C — The design

## C.1 Architecture

```
                    ┌──────────────────────── agent process ────────────────────────┐
                    │                                                               │
  user task ───────►│  LLM plans an action  (tool name + tool input)                 │
                    │             │                                                  │
                    │             ▼                                                  │
                    │   ┌───────────────────────────────────────────┐               │
                    │   │  ①  SENSORS  (materialisation layer)      │   Python,      │
                    │   │     predicates over                       │   impure,      │
                    │   │       user_input, tool_input,             │   arbitrary    │
                    │   │       intermediate_steps                  │                │
                    │   │  → flags: Set<String>                     │                │
                    │   │  → targets: Set<String>  (paths, hosts)   │                │
                    │   │  → risk: Long                             │                │
                    │   └────────────────────┬──────────────────────┘               │
                    │                        ▼                                       │
                    │   ┌───────────────────────────────────────────┐               │
                    │   │  ②  REQUEST BUILDER                        │               │
                    │   │     principal = Agent::"..."               │  + entity      │
                    │   │     action    = Action::"invoke"           │    store       │
                    │   │     resource  = Tool::"PythonREPL"         │    incl.       │
                    │   │     context   = {flags, targets, risk,…}   │    Session     │
                    │   └────────────────────┬──────────────────────┘   (taints)     │
                    │                        ▼                                       │
                    │   ┌───────────────────────────────────────────┐               │
                    │   │  ③  CEDAR  is_authorized()                 │   pure,        │
                    │   │     → Allow | Deny                         │   total,       │
                    │   │     → diagnostics.reasons = policy ids     │   verified     │
                    │   └────────────────────┬──────────────────────┘               │
                    │                        ▼                                       │
                    │   ┌───────────────────────────────────────────┐               │
                    │   │  ④  ADVICE RESOLVER                        │               │
                    │   │     policy ids → @advice annotations       │               │
                    │   │     join over the precedence lattice       │               │
                    │   │  → stop | skip | ask | reflect | substitute│               │
                    │   └────────────────────┬──────────────────────┘               │
                    │                        ▼                                       │
                    │   ⑤  ENFORCER  (reuse AgentSpec's enforcement.py)              │
                    │        + ⑥ TAINT UPDATE: write outcome back into Session       │
                    │                        ▼                                       │
                    │                   tool executes / doesn't                      │
                    └───────────────────────────────────────────────────────────────┘
```

**Key insight:** ①+② are where all the mess lives (regex, AST parsing, path resolution). ③ is small, pure, and verifiable. The thesis argument is that this separation is *the right one*, and you demonstrate it by showing what becomes provable once you draw the line there.

## C.2 The Cedar schema (starting point)

```cedar
namespace AgentGuard {

  entity Session = {
    task:           String,
    step:           Long,
    // path-sensitivity lives here: what has already happened this run
    taints:         Set<String>,   // "read_secret", "fetched_untrusted", "escalated"
    approved:       Set<String>,   // user-approved capability grants this session
    allowed_hosts:  Set<String>,
  };

  entity Agent = {
    framework:  String,            // "langchain" | "strands" | "mcp"
    model:      String,
    autonomy:   Long,              // 0 = supervised … 3 = unattended
    session:    Session,
  };

  entity Tool = {
    name:        String,
    kind:        String,           // "code_exec" | "shell" | "http" | "actuator" | "read_only"
    reversible:  Bool,
  };

  action invoke appliesTo {
    principal: [Agent],
    resource:  [Tool],
    context: {
      input:    String,            // raw tool input, for `like` matching
      flags:    Set<String>,       // ← materialised predicates that fired
      targets:  Set<String>,       // resolved paths / hosts / object names
      risk:     Long,              // aggregate score, 0–100
      step:     Long,
    }
  };

  action finish appliesTo {
    principal: [Agent],
    resource:  [Tool],
    context: { output: String, flags: Set<String> }
  };
}
```

> **Design decision to argue in the thesis:** `flags: Set<String>` is flexible but **the validator cannot catch a typo in a set member**. The alternative — a record of named `Bool`s (`flags: { involve_system_file: Bool, … }`) — *is* fully validated, at the cost of a schema regeneration whenever you add a predicate. Recommendation: **generate the record-of-bools schema from the predicate registry** (a small codegen step, like `gen.py` but sane), so you get full validation *and* extensibility. Measure how many real rule-authoring errors each option catches — that is a publishable micro-result.

## C.3 Policies — the four patterns

**① Baseline capability grant (fail-closed by default).**

```cedar
@id("baseline_read_only")
permit (principal, action == AgentGuard::Action::"invoke", resource)
when { resource.kind == "read_only" };

@id("baseline_code_exec_supervised")
permit (principal, action == AgentGuard::Action::"invoke", resource)
when { resource.kind == "code_exec" && principal.autonomy <= 1 };
```

**② A direct port of an AgentSpec rule** (`manipulate_system_file`):

```cedar
@id("manipulate_system_file")
@advice("user_inspection")
@source("agentspec:src/rules/manual/pythonrepl.ar#index4")
forbid (
  principal,
  action   == AgentGuard::Action::"invoke",
  resource == AgentGuard::Tool::"PythonREPL"
)
when {
  context.flags.contains("involve_system_file") &&
  context.flags.contains("copy_file")
};
```

**③ A *path* property — impossible in AgentSpec, natural here.** Reading a secret is fine. Making an outbound POST is fine. Doing the second *after* the first, to a host nobody approved, is exfiltration:

```cedar
@id("exfiltration_path")
@advice("stop")
forbid (principal, action == AgentGuard::Action::"invoke", resource)
when {
  principal.session.taints.contains("read_secret") &&
  context.flags.contains("submit_post_request") &&
  !context.targets.containsAny(principal.session.allowed_hosts)
};
```

**④ Escalating enforcement by risk and autonomy** — one policy replacing what AgentSpec needs many rules to express:

```cedar
@id("risk_escalation")
@advice("llm_self_reflect")
forbid (principal, action, resource)
when {
  context.risk >= 40 && context.risk < 70 &&
  !resource.reversible &&
  !principal.session.approved.contains(resource.name)
};
```

Also demonstrate **`like`** for the cheap cases that don't need a Python sensor at all — and then discuss honestly why it isn't enough (no alternation, no capture, `*` only):

```cedar
when { context.input like "*os.remove*" }
```

## C.4 The advice lattice (contribution M2)

Cedar can return `Deny` from several policies at once. Each may carry different advice. You need a **deterministic join**:

```
        stop                    (most restrictive)
          │
     user_inspection
          │
    llm_self_reflect
          │
         skip
          │
        allow                   (least restrictive)
```

Rules:
1. If the decision is `Allow` → advice is `allow` (with an optional non-blocking `@warn`).
2. If `Deny` → collect `@advice` from every policy id in `diagnostics.reasons`, take the **join** (most restrictive wins).
3. `invoke_action` / substitution is *not* on the lattice — it's a rewrite, so it may only apply when it is the unique determining policy. Otherwise fall back to `stop`. **State and justify this.**

This gives you a property worth proving: *the enforcement outcome is independent of policy order and of the order sensors ran* — the exact property AgentSpec's `for rule in self.rules: … return` loop does **not** have.

**Implementation risk (spike this early, Week 3):** `cedarpy` exposes `diagnostics.reasons` and `diagnostics.id_annotations_by_reason`. Confirm you can read *arbitrary* annotations (`@advice`), not just `@id`. Fallbacks, in order of preference: (a) build a `policy_id → advice` side-table at load time by parsing annotations yourself, (b) use the Cedar CLI's JSON policy representation, (c) drop to a PyO3 wrapper over `cedar-policy` 4.12 directly.

## C.5 The theory framing (do not skip this — it is what makes it a thesis)

Position the work in **runtime verification**:

- Schneider's **security automata** — truncation only. That is AgentSpec's `stop`.
- Bauer/Ligatti/Walker's **edit automata** — truncation, *suppression*, *insertion*. AgentSpec's `skip` is suppression; `invoke_action` is insertion; `llm_self_reflect` is insertion of a re-planning step.
- Your system = an **edit automaton whose transition relation is a Cedar policy set**, with the automaton's state materialised as a `Session` entity.

That framing lets you say precisely what class of properties you can enforce, and it makes the taint-set design principled rather than a hack. It also sets up the honest limitation: Cedar is per-request, so anything requiring unbounded history must be summarised into finitely many session attributes — i.e. **you enforce safety properties over a finite abstraction of the trace**. Say exactly what is lost.

## C.6 Compiling AgentSpec → Cedar

Write a source-to-source compiler so the existing corpus (and the paper's LLM-generated rules) come along for free.

| AgentSpec | Cedar |
|---|---|
| `rule @name` | `@id("name")` |
| `trigger <Tool>` | `resource == Tool::"<Tool>"` (or `resource in ToolGroup::"…"` for alternation) |
| `trigger any` | omit the resource constraint |
| `trigger finish` / `state_change` | `action == Action::"finish"` etc. |
| `check p q r` | `when { context.flags.contains("p") && … }` |
| `check !p` | `when { !context.flags.contains("p") }` |
| `enforce stop` | `forbid` + `@advice("stop")` |
| `enforce skip` | `forbid` + `@advice("skip")` |
| `enforce user_inspection` | `forbid` + `@advice("user_inspection")` |
| `enforce llm_self_reflect` | `forbid` + `@advice("llm_self_reflect")` |
| `enforce invoke_action(t,{…})` | `forbid` + `@advice("substitute")` `@substitute_tool("t")` `@substitute_args("{…}")` |
| `enforce none` | drop the policy (or emit as a `@warn` audit policy) |

Reuse the existing ANTLR listener (`AgentSpecListener`) as the compiler front end — you get the parse tree for free, and you can extend the `.g4` **once** to fix the B.2 defects (comments, `&`/`|`, dotted and multi-word triggers, open predicate identifiers) before compiling. Fixing the grammar is worth doing precisely because it lets you compile the *whole* corpus and report an honest coverage number.

---

# PART D — The plan

Eight phases. Sized for ~24 weeks (a full master's thesis); the compression note at the end shows how to cut it to 12.

### Phase 0 — Reproduce & measure the baseline · Weeks 1–2

- [ ] Clone, pin dependencies (LangChain 0.3.25 / langchain-core 0.3.81 per the README), get `src/code_agent.py` running end-to-end on **one** RedCode index.
- [ ] Re-run the parse audit of Part B — **`tools/audit_rules.py` ships alongside this document**; run it against your clone and commit the output as a table. **This is Chapter 3's evidence.**
- [ ] Instrument the existing loop: log per-step wall-clock for (LLM plan | predicate evaluation | rule parse | enforcement). You need the *baseline* latency breakdown or the overhead comparison later is meaningless.
- [ ] Record fail-open behaviour (B.3) as a reproducible test case.

**Exit criteria:** you can run the unmodified system, and you have a numeric baseline table for effectiveness *and* latency.

> ⚠️ Do this before touching Cedar. If reproduction takes longer than two weeks (LangChain version drift is a real risk in this repo — deprecated `initialize_agent`, `AgentType`, `langchain_experimental`), **descope AV/Apollo immediately** and say so.

### Phase 1 — Walking skeleton · Week 3

The smallest thing that works end to end. One rule, one tool, one benchmark case, one day.

- [ ] `pip install cedarpy`; write `hello_cedar.py` that authorizes a fake `PythonREPL` call.
- [ ] Spike the annotation-reading question from C.4. **Decide the fallback now.**
- [ ] Hard-code one sensor (`involve_system_file`), one policy, one advice value, and wire it into `ControlledAgentExecutor` behind a feature flag.

**Exit criteria:** a RedCode case that gets blocked by Cedar rather than by AgentSpec's interpreter. Take a screenshot; it goes in the thesis.

### Phase 2 — The engine · Weeks 4–7

- [ ] `agentguard/schema.py` — schema (C.2) + a generator from the predicate registry.
- [ ] `agentguard/sensors.py` — wrap the existing 36 predicates as sensors; a registry with metadata (name, cost, domain, which flags it can set).
- [ ] `agentguard/request.py` — the materialisation layer: `RuleState → (Request, Entities)`.
- [ ] `agentguard/engine.py` — policy set loading, schema validation at startup (**refuse to start on validation failure — this is the anti-fail-open contribution, make it loud**), `is_authorized`, advice resolution + the lattice.
- [ ] `agentguard/enforcer.py` — advice → the existing `enforcement.py` classes.
- [ ] `agentguard/executor.py` — `CedarControlledAgentExecutor`, a drop-in sibling of the original.
- [ ] Unit tests: golden `(request, entities, policies) → (decision, advice)` triples.

**Exit criteria:** feature-flag parity — the same benchmark case behaves identically through either engine.

### Phase 3 — The compiler · Weeks 8–10

- [ ] Fix the `.g4` defects from B.2 (comments; `&`/`|`; dotted/multi-word triggers; `IDENTIFIER` predicates instead of a closed token list; align `llm_self_examine`/`llm_self_reflect`).
- [ ] `agentguard/compile.py` — the C.6 mapping, as an ANTLR listener.
- [ ] Compile all 42 shipped rules + the paper's LLM-generated rules (`src/rules/llm/generated_rules-o1.jsonl`, `-4o.jsonl`).
- [ ] Report coverage: compiled cleanly / compiled with warnings / not expressible. **Every failure is a finding — analyse them, don't hide them.**

**Exit criteria:** a coverage table, and a `.cedar` corpus that passes `validate_policies()`.

### Phase 4 — Path sensitivity · Weeks 11–14 · ⭐ the novel bit

- [ ] Design the taint vocabulary. Start small and defensible: `read_secret`, `read_system_file`, `fetched_untrusted`, `wrote_executable`, `escalated_privilege`, `user_approved_<cap>`.
- [ ] Session lifecycle: create at task start, update after every observation, expose as an entity.
- [ ] Write ≥8 genuinely path-sensitive policies (exfiltration, untrusted-code→execute, approval-then-scope-creep, irreversible-after-failed-precondition).
- [ ] **Construct the evaluation cases yourself.** RedCode/ToolEmu are largely single-action-risky; multi-step harmful *paths* whose individual steps are all benign are under-represented. A curated set of ~30 multi-step scenarios is a genuine artifact contribution — and the honest framing is "we had to build this because existing benchmarks don't test it."
- [ ] Formalise: which fragment of LTL-over-finite-traces do the session attributes let you express? Where does the abstraction lose precision?

**Exit criteria:** cases that the original AgentSpec provably cannot catch, that yours does. **This is the headline result.**

### Phase 5 — Verification · Weeks 15–17 · ⭐ the other novel bit

Requires `cedar-policy-symcc` and **cvc5 1.3.1**. Rust-side; drive it via CLI from Python.

- [ ] **Equivalence**: prove the compiled policy set is equivalent to the hand-written one (validates the compiler).
- [ ] **Conflict / shadowing**: find policies subsumed by others → dead rules in the shipped corpus.
- [ ] **Never-errors**: prove no policy can throw at runtime.
- [ ] **Coverage / reachability**: find the requests no `permit` covers — the fail-closed surface.
- [ ] **Regression gate**: when a policy is edited, does the change strictly narrow or widen? Show a counterexample when it widens.

**Exit criteria:** ≥3 real defects found in the shipped corpus by automated analysis that no AgentSpec tooling could find. This is the single most defensible "Cedar was worth it" argument in the whole thesis — *the baseline has no analysis story at all*.

### Phase 6 — Portability · Weeks 18–19 · optional but cheap

The policy set is now framework-independent. Prove it:

- [ ] Second binding: MCP tool calls (use `cedar-policy-mcp-schema-generator` to generate schemas from MCP tool descriptions), or a Strands intervention.
- [ ] Show the *same* `.cedar` file governing both. One page, high credibility.

### Phase 7 — Evaluation · Weeks 20–22
### Phase 8 — Writing · Weeks 23–26

(Start writing in Week 1. Related work and background can be drafted while Phase 0 runs.)

### If you only have 12 weeks

Keep Phases 0, 1, 2, 4, 5. **Cut** Phase 3 (hand-port 15 representative rules instead of building a compiler) and Phase 6. Drop AV/Apollo entirely; drop embodied unless AI2-THOR installs painlessly. Phases 4 and 5 are where the contribution is — protect them.

---

# PART E — Evaluation

| RQ | Question | Method | Metric | Baseline |
|---|---|---|---|---|
| **RQ1** | Can Cedar express AgentSpec's rules? | Compile the corpus | % compiled / warned / inexpressible; LOC ratio | The 42 shipped rules |
| **RQ2** | Is safety preserved? | RedCode-Exec, ToolEmu (144), SafeAgentBench | Unsafe executions prevented; **false-positive rate on benign tasks** | Unguarded agent; original AgentSpec (>90 % / 100 %) |
| **RQ3** | ⭐ Does path-sensitivity catch more? | Your curated multi-step set + any multi-step ToolEmu cases | Detection rate, split by "single-action risky" vs "path risky" | Original AgentSpec |
| **RQ4** | ⭐ What does analysability buy? | `symcc` over both corpora | # conflicts / shadowed / unreachable / error-prone policies found | **None — the baseline has no such capability** |
| **RQ5** | What does it cost? | Latency instrumentation | µs for `is_authorized`, ms for sensors, % of end-to-end step | AgentSpec's "millisecond-level" |
| **RQ6** | Does it fail closed? | Fault injection: malformed policies, missing attributes, sensor exceptions | # of injected faults yielding an unsafe allow | AgentSpec fails open (B.3) |

**Do not skip false positives.** A guard that blocks everything scores 100 % on RQ2. Every safety number needs a paired utility/benign-task number. ToolEmu's helpfulness score and RedCode's benign variants both give you this.

**RQ5, said plainly in advance:** Cedar evaluation will be microseconds. Sensors will dominate — regex sweeps over generated code. So the honest finding is likely *"the policy engine is free; detection is the cost"*, which is itself a useful result and argues for the layer split. Measure and report them separately.

**Threats to validity to write up honestly:** ToolEmu is an LM-emulated sandbox, not ground truth. Benchmark cases may be in the model's training data. Your curated path set was written by you, who also wrote the policies — mitigate by having someone else write the scenarios, or derive them from CVE/incident reports.

---

# PART F — Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| **LangChain drift** — repo pins 0.3.x, uses deprecated `initialize_agent`/`AgentType` | High | Pin exactly per README. Timebox Phase 0 to 2 weeks. If it fails, build the executor against LCEL or Strands and treat AgentSpec as a *reference implementation* rather than a base. |
| `cedarpy` (4.8.7) trails Cedar (4.12) | Medium | Features you need are old and stable. Fallback: Rust CLI subprocess, or your own PyO3 wrapper. Spike in Week 3. |
| `@advice` annotations not readable from Python | Medium | Side-table built at load time by parsing annotations. Trivial. Spike in Week 3. |
| cvc5 / `symcc` toolchain pain | Medium | Isolate to Phase 5; run it in Docker; it's offline analysis, not on the hot path. |
| **Scope creep into AV/Apollo** | High | The AV path uses a different mechanism entirely (parameter rewriting, not veto — see `translator.py`). **Declare it out of scope in Chapter 1** and mention it as future work. |
| AI2-THOR install pain (`ai2thor` needs a display / GPU) | Medium | Xvfb headless, or replay the recorded trajectories in `expres/embodied/*.jsonl` offline. Offline replay is sufficient for RQ1/RQ3/RQ4. |
| "Isn't this just Bedrock AgentCore?" | **High — expect this in the defence** | Prepare the one-line answer from A.2: they authorize *one call from its arguments*; you reason over *trajectories* and support *non-binary enforcement*. Have RQ3 and RQ4 numbers ready. |
| Set-of-strings flags defeat schema validation | Medium | Generate the record-of-bools schema (C.2); measure both. |
| LLM API cost for full benchmark runs | Medium | Cache trajectories. Most of RQ1/RQ3/RQ4 can run on *replayed* traces without any LLM calls. Budget the live runs. |

---

# PART G — Thesis outline

1. **Introduction** — agent autonomy, the harm surface, why guardrails-in-the-prompt fail, contributions, RQ list
2. **Background** — LLM agents & the ReAct loop; runtime verification (security automata → edit automata); authorization & Cedar
3. **Motivation & problem analysis** — ⭐ the Part B audit; fail-open behaviour; the analysability gap
4. **Design** — the layered architecture; schema; the advice lattice + its order-independence property; session taint model & its trace-property fragment
5. **Implementation** — the compiler; sensors; the executor; the verification pipeline
6. **Evaluation** — RQ1–RQ6
7. **Discussion** — what Cedar cannot express and why that's acceptable; where the abstraction leaks; deployment implications
8. **Related work** — AgentSpec; ToolEmu/RedCode/SafeAgentBench; Cedar-for-agents (AgentCore, Strands, AutoCedar); runtime verification; guardrail systems (NeMo Guardrails, Llama Guard)
9. **Conclusion & future work** — AV domain; learned policies; multi-agent delegation chains

---

# PART H — Week 1 checklist

```bash
git clone https://github.com/haoyuwang99/AgentSpec.git && cd AgentSpec
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirement.txt
```

Then, in order:

1. Read `src/controlled_agent_excector.py:_iter_next_step` line by line. **That single method is the entire integration surface.** Nothing else in the repo matters as much.
2. Read `src/interpreter.py:verify_and_enforce` and note the re-parse-per-action.
3. Reproduce the parse audit (Part B): `python tools/audit_rules.py AgentSpec/src`. It emits the Part B tables as Markdown; commit them.
4. Get **one** RedCode case running end to end with **one** rule. Nothing else until this works.
5. `pip install cedarpy` and get `is_authorized` returning `Allow` on a toy request.
6. Spike the annotation question (C.4). Write down the answer.
7. Start the thesis document. Draft Chapter 2 background while Phase 0 grinds.

**A note on working style:** the repo has no tests, no CI, `.DS_Store` files committed, `__pycache__` in version control, and a typo in a core filename (`controlled_agent_excector.py`). Do not fight it — fork it, add `pytest` and a CI workflow for *your* code, and keep your contribution in a clean `agentguard/` package that imports from `src/`. Being able to say "the original had no test suite; ours has N tests and a verification gate" is itself a defensible engineering contribution.

---

# PART I — Reading & links

**Primary**
- AgentSpec paper — <https://arxiv.org/abs/2503.18666> (ICSE 2026)
- AgentSpec repo — <https://github.com/haoyuwang99/AgentSpec>
- Cedar docs — <https://docs.cedarpolicy.com/> · policy syntax & annotations: <https://docs.cedarpolicy.com/policies/syntax-policy.html>
- Cedar repo — <https://github.com/cedar-policy/cedar> · crate: <https://crates.io/crates/cedar-policy> (4.12.0)
- `cedar-policy-symcc` (SMT verification) — <https://crates.io/crates/cedar-policy-symcc> · docs: <https://docs.rs/cedar-policy-symcc>
- `cedar-spec` (Lean models) — <https://github.com/cedar-policy/cedar-spec>
- `cedarpy` (Python bindings) — <https://github.com/k9securityio/cedar-py> (4.8.7)

**Cedar for agents — the prior art you must differentiate from**
- `cedar-policy/cedar-for-agents` — <https://github.com/cedar-policy/cedar-for-agents>
- Why AgentCore Policy chose Cedar — <https://aws.amazon.com/blogs/security/why-policy-in-amazon-bedrock-agentcore-chose-cedar-for-securing-agentic-workflows/>
- Least-privilege in multi-agent chains — <https://aws.amazon.com/blogs/security/enforce-least-privilege-authorization-in-multi-agent-ai-chains-using-cedar/>
- Strands `CedarAuthorization` — <https://strandsagents.com/docs/user-guide/concepts/agents/interventions/cedar-authorization/>
- AutoCedar (verifier-guided policy synthesis) — <https://arxiv.org/pdf/2607.03656>

**Benchmarks**
- ToolEmu — LM-emulated sandbox, 144 cases / 38 toolkits (vendored in `benchmarks/ToolEmu/`)
- RedCode-Exec — 27 risky-scenario indices × 30 programs
- SafeAgentBench — embodied safety, AI2-THOR

**Theory**
- Schneider, *Enforceable Security Policies* (security automata)
- Ligatti, Bauer & Walker, *Edit Automata* — the formal home for `stop`/`skip`/`invoke_action`
- Bartocci & Falcone (eds.), *Lectures on Runtime Verification*

---

## One last thing

The weakest version of this thesis is "I swapped one rule language for another and the numbers stayed the same." That is a refactor, not research.

The strong version is: **"AgentSpec's rules cannot be checked, cannot be composed order-independently, cannot reason about execution paths, and fail open. I show all four empirically, fix all four with a formally-grounded policy engine, and prove properties of the resulting rule sets that no prior agent-guardrail system can state, let alone prove."**

Phases 4 and 5 are that thesis. Everything before them is setup. Protect their calendar time.
