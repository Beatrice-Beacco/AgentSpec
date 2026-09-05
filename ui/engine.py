"""Engine layer for the AgentSpec test bench.

Three jobs:

  1. parse-check rule text and report errors the way ANTLR sees them
  2. explain *why* a rule did or did not fire (per-predicate diagnostics)
  3. run the real ControlledAgentExecutor against a scripted action and
     report what actually happened

The agent is driven by FakeListLLM, so no API key is needed and the same
input always produces the same run. That is deliberate: this bench tests the
rule engine, not the LLM. A non-deterministic agent would make it useless as
a regression tool.
"""
import io
import os
import re
import sys
import contextlib
import builtins
import traceback

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener
from langchain.tools import Tool
from langchain_core.language_models.fake import FakeListLLM

from spec_lang.AgentSpecLexer import AgentSpecLexer
from spec_lang.AgentSpecParser import AgentSpecParser
from controlled_agent_excector import initialize_controlled_agent
from rule import Rule
from rules.manual.table import predicate_table


# --------------------------------------------------------------------- parse

class _Collect(ErrorListener):
    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, sym, line, column, msg, e):
        self.errors.append({"line": line, "column": column, "message": msg})


def parse_errors(text):
    """Every lexer + parser syntax error in `text`.

    ANTLR recovers rather than raising, and AgentSpec's own Rule.from_text
    leaves the default console listener in place, so errors are invisible
    unless collected explicitly. That is the fail-open bug (plan.md S0.12).
    """
    lexer = AgentSpecLexer(InputStream(text))
    lexer.removeErrorListeners()
    lex = _Collect()
    lexer.addErrorListener(lex)

    parser = AgentSpecParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    par = _Collect()
    parser.addErrorListener(par)

    parser.program()
    return lex.errors + par.errors


def strip_comments(text):
    """The grammar has no comment token, so // lines must go before parsing."""
    return re.sub(r"//.*", "", text)


def split_rules(text):
    """Split a multi-rule document into individual rule sources.

    Necessary because RuleParser is a listener that overwrites its fields on
    each `rule` node, so Rule.from_text on a multi-rule document silently
    returns only the last one.
    """
    body = strip_comments(text)
    return ["rule @" + chunk for chunk in body.split("rule @")[1:]]


CLAUSE = r"^{}\s*\n((?:\s+\S.*\n?)*)"


def clause(source, name):
    """Return the indented body of a `trigger` / `check` / `enforce` clause."""
    m = re.search(CLAUSE.format(name), source, re.M)
    if not m:
        return []
    return [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]


def load_rules(text):
    """Parse rule text into [{id, source, errors, trigger, checks, enforce}].

    Never raises: a rule that fails to parse comes back with its errors
    attached, because seeing the error is the point of the bench.
    """
    out = []
    for source in split_rules(text):
        errors = parse_errors(source)
        m = re.search(r"rule\s+@(\w+)", source)
        entry = {
            "id": m.group(1) if m else "<unnamed>",
            "source": source.strip(),
            "errors": errors,
            "trigger": (clause(source, "trigger") or ["<none>"])[0],
            "checks": clause(source, "check"),
            "enforce": clause(source, "enforce"),
            "rule": None,
        }
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                entry["rule"] = Rule.from_text(source)
        except Exception as exc:                       # noqa: BLE001
            entry["errors"] = errors + [
                {"line": 0, "column": 0, "message": f"{type(exc).__name__}: {exc}"}
            ]
        out.append(entry)
    return out


# --------------------------------------------------------------- diagnostics

def probe_predicates(user_input, tool_input, intermediate_steps, only=None):
    """Evaluate predicates against an input and report which ones fire.

    This is the diagnostic AgentSpec does not have: it answers "why didn't my
    rule fire?" without adding print statements to the interpreter. Cedar
    gives the equivalent for free via diagnostics.reasons.

    Predicates are third-party Python and some index into intermediate_steps
    assuming a shape they may not get, so every call is contained.
    """
    names = sorted(only) if only else sorted(predicate_table)
    results = []
    for name in names:
        func = predicate_table.get(name)
        if func is None:
            results.append({"name": name, "value": None,
                            "error": "not registered in predicate_table"})
            continue
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                value = bool(func(user_input, tool_input, intermediate_steps))
            results.append({"name": name, "value": value, "error": None})
        except Exception as exc:                       # noqa: BLE001
            results.append({"name": name, "value": None,
                            "error": f"{type(exc).__name__}: {exc}"})
    return results


def explain(rules, user_input, tool_name, tool_input, intermediate_steps):
    """Per-rule dry run: would this rule fire, and on the strength of what?

    Evaluates trigger and predicates without applying any enforcement, so it
    is safe to call on rules whose enforcement would block or prompt.
    """
    report = []
    for entry in rules:
        rule = entry["rule"]
        triggered = False
        if rule is not None:
            try:
                triggered = bool(rule.triggered(tool_name, tool_input))
            except Exception as exc:                   # noqa: BLE001
                triggered = f"error: {type(exc).__name__}: {exc}"

        checks = []
        if triggered is True:
            for raw in entry["checks"]:
                negated = raw.startswith("!")
                name = raw.lstrip("!").strip()
                if name in ("true", "false"):
                    value, error = name == "true", None
                else:
                    probe = probe_predicates(
                        user_input, tool_input, intermediate_steps, only=[name]
                    )[0]
                    value, error = probe["value"], probe["error"]
                effective = (not value) if (negated and value is not None) else value
                checks.append({"raw": raw, "predicate": name, "negated": negated,
                               "value": value, "effective": effective, "error": error})

        would_fire = triggered is True and bool(checks) and all(
            c["effective"] is True for c in checks
        )
        report.append({
            "id": entry["id"],
            "trigger": entry["trigger"],
            "triggered": triggered,
            "checks": checks,
            "enforce": entry["enforce"],
            "would_fire": would_fire,
            "errors": entry["errors"],
        })
    return report


# ---------------------------------------------------------------------- run

def react_script(tool_name, tool_input, final="done"):
    return [
        f"Thought: I should use the tool.\n"
        f"Action: {tool_name}\n"
        f"Action Input: {tool_input}",
        f"Thought: I have the answer.\nFinal Answer: {final}",
    ]


def run(rule_text, user_input, tool_name, tool_input,
        intermediate_steps=None, approve=True):
    """Run the real ControlledAgentExecutor against one scripted action.

    `approve` answers any `user_inspection` prompt, which would otherwise
    block the server on stdin forever. Toggling it is how you exercise both
    branches of a user_inspection rule from the browser.
    """
    intermediate_steps = intermediate_steps or []
    rules = load_rules(rule_text)
    parsed = [e["rule"] for e in rules if e["rule"] is not None]

    tool_calls = []

    def _record(command):
        tool_calls.append(command)
        return "OK"

    tool = Tool(name=tool_name, description="Test bench tool.", func=_record)
    agent = initialize_controlled_agent(
        [tool],
        FakeListLLM(responses=react_script(tool_name, tool_input)),
        agent="zero-shot-react-description",
        rules=parsed,
        verbose=True,
        max_iterations=3,
    )

    trace = io.StringIO()
    real_input = builtins.input
    builtins.input = lambda *_a, **_k: "yes" if approve else "no"
    try:
        with contextlib.redirect_stdout(trace):
            result = agent.invoke(user_input)
        error = None
    except Exception:                                   # noqa: BLE001
        result, error = {"output": "", "intermediate_steps": []}, traceback.format_exc()
    finally:
        builtins.input = real_input

    steps = [
        {"tool": a.tool, "input": a.tool_input, "observation": str(o)}
        for a, o in result.get("intermediate_steps", [])
    ]
    output = result.get("output", "")

    if error:
        verdict = "ERROR"
    elif "action stopped by" in output:
        verdict = "STOPPED"
    elif not tool_calls and any("skipped by" in s["observation"] for s in steps):
        verdict = "SKIPPED"
    elif tool_calls:
        verdict = "ALLOWED"
    else:
        verdict = "NO ACTION"

    return {
        "verdict": verdict,
        "output": output,
        "tool_calls": tool_calls,
        "steps": steps,
        "trace": _clean(trace.getvalue()),
        "error": error,
        "rules": [{"id": e["id"], "errors": e["errors"]} for e in rules],
        "explain": explain(rules, user_input, tool_name, tool_input, intermediate_steps),
        # Cedar lands in Sprint 1/2 (plan.md S1.7, S2.5). The shape is fixed now
        # so the UI does not need restructuring when it does.
        "cedar": {"status": "not_implemented",
                  "note": "Cedar decisions appear here after plan.md S1.7."},
    }


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _clean(text):
    return ANSI.sub("", text).strip()
