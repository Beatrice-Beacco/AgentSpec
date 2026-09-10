"""AgentSpec rule -> Cedar policy (plan.md S3.3, thesis §C.6).

Reads the corpus with the permissive grammar (S3.1) and emits Cedar. The mapping
is the table in §C.6, adjusted where the record schema (S2.2) differs from the
`Set<String>` the table assumed:

    rule @name                  @id("name")
    trigger <Tool>              resource == Tool::"<Tool>"
    trigger A | B               when { resource in [Tool::"A", Tool::"B"] }
    trigger any                 no resource constraint at all
    check p                     context.flags has p && context.flags.p
    check !p                    context.flags has p && !context.flags.p
    enforce stop                forbid + @advice("stop")
    enforce skip                forbid + @advice("skip")
    enforce user_inspection     forbid + @advice("user_inspection")
    enforce llm_self_reflect    forbid + @advice("llm_self_reflect")
    enforce invoke_action(t,{}) forbid + @advice("substitute") @substitute_tool @substitute_args
    enforce none                dropped -- there is nothing to forbid

`check !p` is the one worth reading twice. It compiles to "p was evaluated *and*
came back false", not "p is absent". Those are different facts under the record
schema, and the second would make the rule fire whenever the sensor had not run
-- which is the opposite of what the author asked for.

**Not compiling is a result, not a failure of the compiler.** Every rule comes
back as a `Compiled`, and one that cannot be expressed carries the reason why.
Those reasons *are* RQ1: `docs/coverage.md` (S3.5) is a table of them, and a
compiler that silently dropped them would be answering the wrong question.
"""
import ast
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional, Tuple

import agentguard  # noqa: F401  -- puts src/ on sys.path

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from agentguard import advice as ag_advice
from agentguard import sensors as sensor_registry
from agentguard.speclang.AgentSpecFullLexer import AgentSpecFullLexer
from agentguard.speclang.AgentSpecFullListener import AgentSpecFullListener
from agentguard.speclang.AgentSpecFullParser import AgentSpecFullParser

NAMESPACE = "AgentGuard"
INVOKE = f'{NAMESPACE}::Action::"invoke"'

#: Events that are not a tool invocation. The schema has one action, `invoke`;
#: `action finish` and friends were deferred and never added, so a rule
#: triggered on one of these has nothing to compile to.
NON_INVOKE_EVENTS = {"state_change", "before_action", "after_action", "finish"}

#: `trigger act TerminalExecute` -- a keyword from the language the examples
#: describe and the grammar never implemented (docs/findings.md D-10). Our
#: permissive grammar reads it as the first word of a two-word event name, so it
#: has to come off here or the tool would be `"act TerminalExecute"`.
EVENT_PREFIXES = {"act"}

#: `llm_self_examine` is what the README and toolemu.ar write; the shipped
#: grammar declares `llm_self_reflect`. Same outcome, two names (D-7).
ENFORCEMENT_ALIASES = {"llm_self_examine": ag_advice.LLM_SELF_REFLECT}


class CompileError(ErrorListener):
    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, sym, line, column, msg, e):
        self.errors.append(f"L{line}:{column} {msg}")


# --------------------------------------------------------------------- IR


@dataclass(frozen=True)
class Check:
    name: str
    negated: bool = False
    #: A parameterised predicate such as `v_f_disL(10)`. There is no flag for
    #: it -- the registry has no notion of an argument -- so it cannot compile.
    parameterised: bool = False
    literal: Optional[bool] = None      # `true` / `True` / `false`


@dataclass(frozen=True)
class Enforcement:
    kind: str                            # an advice name, "invoke_action", "config"
    text: str
    message: Optional[str] = None
    tool: Optional[str] = None
    args: Optional[str] = None


@dataclass(frozen=True)
class RuleIR:
    """One parsed rule, before any decision about whether it can be expressed."""
    id: str
    events: Tuple[str, ...] = ()         # alternatives, already normalised
    checks: Tuple[Check, ...] = ()
    enforcements: Tuple[Enforcement, ...] = ()


@dataclass(frozen=True)
class Compiled:
    """A rule's fate: either a policy, or every reason it could not become one.

    `reasons` is a tuple rather than a sentence because S3.5 counts them. A rule
    can be blocked by its trigger, its predicate *and* its enforcement at once --
    every apollo rule is -- and a coverage table that reported only the first
    would understate what bringing it across would take.
    """
    rule_id: str
    source: str
    policy: Optional[str] = None
    reasons: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    ir: Optional[RuleIR] = None
    #: Which sensor domain the policy belongs to, from the flags it reads.
    #: `None` when it reads none (`check true`), so it fits any domain.
    #:
    #: S3.4 has to partition the generated policies by this. An engine runs one
    #: domain's sensors (S2.3), and the startup coverage check refuses a policy
    #: keyed on a flag it will never materialise -- so the whole corpus in one
    #: file does not load, and should not.
    domain: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.policy is not None

    @property
    def reason(self) -> Optional[str]:
        """The reasons as one sentence, for a log line."""
        return "; ".join(self.reasons) if self.reasons else None


# ------------------------------------------------------------------ parsing


class _Collector(AgentSpecFullListener):
    """Walks one rule and gathers the IR. Nothing here decides anything."""

    def __init__(self):
        self.id = None
        self.events = []
        self.checks = []
        self.enforcements = []

    def enterRuleClause(self, ctx):
        self.id = ctx.IDENTIFIER().getText()

    def enterEvent(self, ctx):
        for term in ctx.eventTerm():
            words = [path.getText() for path in term.eventPath()]
            while words and words[0] in EVENT_PREFIXES:
                words.pop(0)
            if words:
                self.events.append(" ".join(words))

    def enterCheckClause(self, ctx):
        for node in ctx.predicate():
            self.checks.append(_read_check(node))

    def enterEnforceClause(self, ctx):
        for node in ctx.enforcement():
            self.enforcements.append(_read_enforcement(node))


def _read_check(ctx, negated=False):
    if ctx.NOT() is not None:
        return _read_check(ctx.predicate(), not negated)
    if ctx.TRUE() is not None:
        return Check(name=ctx.getText(), negated=negated, literal=True)
    if ctx.FALSE() is not None:
        return Check(name=ctx.getText(), negated=negated, literal=False)
    if ctx.predicateFunc() is not None:
        return Check(name=ctx.predicateFunc().IDENTIFIER().getText(),
                     negated=negated, parameterised=True)
    return Check(name=ctx.IDENTIFIER().getText(), negated=negated)


def _read_enforcement(ctx):
    text = ctx.getText()
    if ctx.config() is not None:
        return Enforcement(kind="config", text=text)
    if ctx.actionInvoke() is not None:
        call = ctx.actionInvoke()
        args = {}
        for pair in call.kvPair():
            key = pair.STRING().getText().strip('"')
            args[key] = pair.value().getText().strip('"')
        return Enforcement(kind="invoke_action", text=text,
                           tool=call.IDENTIFIER().getText(),
                           args=json.dumps(args, sort_keys=True))
    word = ctx.ENFORCEMENT().getText()
    message = ctx.STRING().getText().strip('"') if ctx.STRING() is not None else None
    return Enforcement(kind=ENFORCEMENT_ALIASES.get(word, word), text=text,
                       message=message)


def parse_rule(text):
    """(RuleIR or None, [syntax errors])."""
    lexer = AgentSpecFullLexer(InputStream(text))
    lexer.removeErrorListeners()
    lex_errors = CompileError()
    lexer.addErrorListener(lex_errors)

    parser = AgentSpecFullParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parse_errors = CompileError()
    parser.addErrorListener(parse_errors)

    tree = parser.program()
    errors = lex_errors.errors + parse_errors.errors
    if errors:
        return None, errors

    from antlr4 import ParseTreeWalker                    # noqa: PLC0415
    collector = _Collector()
    ParseTreeWalker().walk(collector, tree)
    if collector.id is None:
        return None, ["no rule clause"]
    return RuleIR(id=collector.id, events=tuple(collector.events),
                  checks=tuple(collector.checks),
                  enforcements=tuple(collector.enforcements)), []


# ------------------------------------------------------------------ emitting


def _escape(value: str) -> str:
    """Escape a name for a Cedar entity uid, as agentguard/request.py does."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _resource_clause(events):
    """(scope fragment, extra `when` condition) for a trigger.

    A single tool goes in the policy scope, where Cedar can index on it. An
    alternation cannot -- the scope takes one entity uid -- so it moves into the
    condition as `resource in [...]`.
    """
    if not events or events == ("any",):
        return "resource", None
    if len(events) == 1:
        return f'resource == {NAMESPACE}::Tool::"{_escape(events[0])}"', None
    listed = ", ".join(f'{NAMESPACE}::Tool::"{_escape(e)}"' for e in events)
    return "resource", f"resource in [{listed}]"


def _flag_condition(check: Check) -> str:
    """`check p` and `check !p`, under the record schema.

    Both require the sensor to have *run*. Compiling `!p` to `!(flags has p)`
    would make the rule fire whenever nobody looked, which inverts its meaning.
    """
    guard = f"context.flags has {check.name}"
    if check.negated:
        return f"{guard} && !context.flags.{check.name}"
    return f"{guard} && context.flags.{check.name}"


def _unsupported(ir, source, reasons, warnings=()):
    return Compiled(rule_id=ir.id, source=source, reasons=tuple(reasons),
                    warnings=tuple(warnings), ir=ir)


def _domain_of(checks):
    """(domain or None, warnings) for the flags a rule reads."""
    domains = {sensor_registry.SENSORS[c.name].domain
               for c in checks
               if c.literal is None and not c.parameterised
               and c.name in sensor_registry.SENSORS}
    if not domains:
        return None, ()
    if len(domains) == 1:
        return domains.pop(), ()
    return None, (f"reads flags from several domains ({', '.join(sorted(domains))}); "
                  "an engine runs one, so this rule can never fire",)


def to_policy(ir: RuleIR, source: str, known_flags=None) -> Compiled:
    """One RuleIR -> a Cedar policy, or **every** reason it cannot become one.

    All the reasons, not the first: an apollo rule fails on its trigger, its
    predicate and its enforcement independently, and a coverage table that
    showed only the first would understate what it would take to bring the rule
    across. S3.5 is an analysis of these, so they have to be complete.
    """
    known_flags = set(sensor_registry.FLAGS if known_flags is None else known_flags)
    reasons, warnings = [], []

    # --- trigger
    non_invoke = sorted({e for e in ir.events if e in NON_INVOKE_EVENTS})
    if non_invoke:
        reasons.append(
            f"triggers on {', '.join(non_invoke)}, and the schema declares only "
            "`action invoke`")
    scope_resource, resource_condition = _resource_clause(ir.events)

    # --- enforce
    actionable = [e for e in ir.enforcements if e.kind != "config"]
    configs = [e for e in ir.enforcements if e.kind == "config"]
    enforcement = None
    if not actionable:
        reasons.append(
            f"enforcement is {len(configs)} `config` assignment(s), which Cedar has "
            "no equivalent for -- they set planner parameters rather than guard "
            "an action")
    elif len(actionable) > 1:
        reasons.append(
            "names several enforcements "
            f"({', '.join(e.kind for e in actionable)}) and which applies is "
            "undefined in AgentSpec too, since the interpreter looks the whole "
            "clause text up as one key")
    else:
        enforcement = actionable[0]
        if configs:
            warnings.append(f"dropped {len(configs)} `config` assignment(s)")
        if enforcement.kind == "none":
            reasons.append(
                "`enforce none` -- the rule matches and then chooses not to act, "
                "so there is nothing to forbid")
            enforcement = None
        elif enforcement.kind == "invoke_action" and not enforcement.tool:
            reasons.append("invoke_action names no tool")
            enforcement = None
        elif (enforcement.kind != "invoke_action"
              and enforcement.kind not in ag_advice.LATTICE):
            reasons.append(f"`enforce {enforcement.kind}` is not an enforcement outcome")
            enforcement = None

    # --- check
    conditions = []
    if resource_condition:
        conditions.append(resource_condition)

    unknown, parameterised, never = [], [], False
    for check in ir.checks:
        if check.literal is True:
            continue                        # `check true` adds no condition
        if check.literal is False:
            never = True
            continue
        if check.parameterised:
            parameterised.append(check.name)
            continue
        if check.name not in known_flags:
            unknown.append(check.name)
            continue
        conditions.append(_flag_condition(check))

    if parameterised:
        reasons.append(
            f"parameterised predicate {', '.join(sorted(set(parameterised)))}(...) -- "
            "sensors are nullary, so there is no flag to test")
    if unknown:
        reasons.append(
            f"no registered sensor produces {', '.join(sorted(set(unknown)))}")
    if never:
        warnings.append("`check false` -- this rule can never fire")
        conditions.append("false")
    if not ir.checks:
        warnings.append("no check clause -- fires on every matching action")

    if reasons or enforcement is None:
        return _unsupported(ir, source, reasons or ("no usable enforcement",),
                            warnings)

    annotations = [f'@id("{ir.id}")']
    if enforcement.kind == "invoke_action":
        annotations.append(f'@advice("{ag_advice.SUBSTITUTE}")')
        annotations.append(f'@{ag_advice.TOOL_ANNOTATION}("{enforcement.tool}")')
        annotations.append(
            f"@{ag_advice.ARGS_ANNOTATION}('{enforcement.args or '{}'}')")
    else:
        annotations.append(f'@advice("{enforcement.kind}")')
        if enforcement.message:
            annotations.append(f'@message("{_escape(enforcement.message)}")')
    annotations.append(f'@source("{source}")')

    body = "\n".join(annotations) + "\nforbid (\n  principal,\n"
    body += f"  action   == {INVOKE},\n  {scope_resource}\n)"
    if conditions:
        joined = " &&\n  ".join(conditions)
        body += "\nwhen {\n  " + joined + "\n}"
    domain, domain_warnings = _domain_of(ir.checks)
    return Compiled(rule_id=ir.id, source=source, policy=body + ";\n",
                    warnings=tuple(warnings) + domain_warnings, ir=ir,
                    domain=domain)


# ------------------------------------------------------------------ driving


def split_rules(text):
    """The corpus, the way a compiler sees it (matches tools/audit_rules.py)."""
    chunks = ["rule @" + c for c in re.sub(r"//.*", "", text).split("rule @")[1:]]
    return [c[:c.index("\nend") + 4] if "\nend" in c else c for c in chunks]


def compile_text(text, source="agentspec:<text>", known_flags=None):
    """Compile every rule in `text`. Always returns one Compiled per rule."""
    out = []
    for chunk in split_rules(text):
        named = re.search(r"rule\s+@(\w+)", chunk)
        rule_id = named.group(1) if named else "<unnamed>"
        ir, errors = parse_rule(chunk)
        if ir is None:
            out.append(Compiled(rule_id=rule_id, source=f"{source}#{rule_id}",
                                reasons=(f"does not parse: {errors[0]}",)))
            continue
        out.append(to_policy(ir, f"{source}#{rule_id}", known_flags))
    return out


def compile_file(path, known_flags=None):
    with open(path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    rel = os.path.relpath(path, agentguard.REPO_ROOT).replace(os.sep, "/")
    return compile_text(text, f"agentspec:{rel}", known_flags)


# ----------------------------------------------- the LLM-generated corpus


def predicate_names(source: str) -> Tuple[str, ...]:
    """The function names defined in a predicate source string.

    **Parsed, never executed.** These are model-written Python that arrives in a
    data file; running it to find out what it is called would be exactly the
    class of thing this project exists to prevent. `ast.parse` is enough.
    """
    try:
        tree = ast.parse(source.strip())
    except SyntaxError:
        return ()
    return tuple(node.name for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef))


def llm_rule_ir(record) -> Tuple[Optional[RuleIR], Tuple[str, ...]]:
    """(RuleIR, problems) for one record of generated_rules-*.jsonl.

    These rules are not DSL text. Each carries its trigger, its enforcement, and
    the **source of its own predicates** -- so unlike the shipped corpus, whose
    rules name predicates that often do not exist anywhere (D-3), these bring
    theirs with them. That is the interesting difference, and it is why they
    compile at a completely different rate.
    """
    name = record.get("name")
    if not name:
        return None, ("record has no name",)

    checks, problems = [], []
    for source in record.get("predicates", ()):
        found = predicate_names(source)
        if not found:
            problems.append("a predicate's source does not parse as Python")
            continue
        # A predicate block may define helpers; the rule's check is the last
        # function defined, which is the one the generator emits as the entry
        # point.
        checks.append(Check(name=found[-1]))

    event = record.get("event")
    enforcement = record.get("enforcement")
    if not enforcement:
        problems.append("record has no enforcement")

    return RuleIR(
        id=name,
        events=(event,) if event else (),
        checks=tuple(checks),
        enforcements=(Enforcement(kind=ENFORCEMENT_ALIASES.get(enforcement,
                                                               enforcement),
                                  text=str(enforcement)),) if enforcement else (),
    ), tuple(problems)


def compile_llm_file(path, known_flags=None):
    """Compile one generated_rules-*.jsonl.

    `known_flags` defaults to the registry *plus* every predicate these rules
    define -- because they define them. Pass the registry alone to measure how
    many would compile without registering anything new.
    """
    with open(path, encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]

    if known_flags is None:
        known_flags = set(sensor_registry.FLAGS)
        for record in records:
            for source in record.get("predicates", ()):
                known_flags.update(predicate_names(source))

    rel = os.path.relpath(path, agentguard.REPO_ROOT).replace(os.sep, "/")
    out = []
    for record in records:
        ir, problems = llm_rule_ir(record)
        source = f"agentspec:{rel}#{record.get('name', '<unnamed>')}"
        if ir is None or problems:
            out.append(Compiled(rule_id=record.get("name", "<unnamed>"),
                                source=source, reasons=problems or ("unreadable",),
                                ir=ir))
            continue
        out.append(to_policy(ir, source, known_flags))
    return out


def llm_flags(paths) -> Tuple[str, ...]:
    """Every flag the generated rules define, sorted. Input to the schema."""
    found = set()
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                for source in json.loads(line).get("predicates", ()):
                    found.update(predicate_names(source))
    return tuple(sorted(found))
