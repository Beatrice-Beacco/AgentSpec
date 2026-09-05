"""Grammar probes: what AgentSpec's DSL does and does not accept today.

Every case here is drawn from syntax that appears in the repo's own rule files
or README. The ones marked xfail are the reason 21 of the 42 shipped rules do
not parse under their own grammar (see docs/baseline-audit.md, tools/audit_rules.py).

The xfails are `strict=True` on purpose. When S3.1 fixes the grammar these
turn into XPASS failures, forcing this file to be updated in the same commit --
the suite tracks the grammar instead of quietly drifting from it.

Kept separate from tools/audit_rules.py, which stays a standalone CLI producing
frozen evidence for the thesis; this file is the tripwire.
"""
import pytest
from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from spec_lang.AgentSpecLexer import AgentSpecLexer
from spec_lang.AgentSpecParser import AgentSpecParser


class _Collect(ErrorListener):
    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, sym, line, column, msg, e):
        self.errors.append(f"L{line}:{column} {msg}")


def parse_errors(text):
    """Parse rule text, returning every lexer and parser syntax error.

    ANTLR recovers from errors rather than raising, and AgentSpec's own
    Rule.from_text leaves the default console listener in place -- so errors
    have to be collected explicitly to be observable at all.
    """
    lexer = AgentSpecLexer(InputStream(text))
    lexer.removeErrorListeners()
    lex_errors = _Collect()
    lexer.addErrorListener(lex_errors)

    parser = AgentSpecParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parse_errors_ = _Collect()
    parser.addErrorListener(parse_errors_)

    parser.program()
    return lex_errors.errors + parse_errors_.errors


def rule(trigger="PythonREPL", check="true", enforce="stop", prefix=""):
    return (
        f"{prefix}rule @r\n"
        f"trigger\n    {trigger}\n"
        f"check\n    {check}\n"
        f"enforce\n    {enforce}\n"
        f"end\n"
    )


# ------------------------------------------------------------------ supported

SUPPORTED = {
    "baseline": rule(check="involve_system_file"),
    "lowercase true": rule(check="true"),
    "negation": rule(check="!involve_system_file"),
    "llm_self_reflect": rule(enforce="llm_self_reflect"),
    "invoke_action": rule(enforce='invoke_action(t, {"a": "b"})'),
    "lifecycle trigger": rule(trigger="state_change"),
}


@pytest.mark.parametrize("source", SUPPORTED.values(), ids=list(SUPPORTED))
def test_supported_syntax_parses(source):
    assert parse_errors(source) == []


# ---------------------------------------------------------------- limitations
# name -> (source, why it matters)

LIMITATIONS = {
    "comment": (
        rule(prefix="//index1\n"),
        "no comment token in AgentSpec.g4; every .ar file uses // comments",
    ),
    "predicate outside token list": (
        rule(check="is_malware"),
        "PREDICATE is a closed 36-alternative token, so adding a check "
        "requires regenerating the parser (README documents this)",
    ),
    "capitalised True": (
        rule(check="True"),
        "toolemu.ar writes `check True`; the grammar only accepts lowercase",
    ),
    "dotted trigger": (
        rule(trigger="Gmail.SendMail"),
        "toolemu.ar uses Toolkit.Action triggers; event is a bare IDENTIFIER",
    ),
    "trigger alternation": (
        rule(trigger="Gmail.SendMail | Twilio.SendSms"),
        "toolemu.ar uses | to share one rule across tools; no such operator",
    ),
    "multi-word trigger": (
        rule(trigger="turn on"),
        "embodied.ar triggers on robot verbs like `turn on`; Rule.triggered "
        "supports them at runtime but the grammar does not",
    ),
    "conjunction with &": (
        rule(trigger="state_change", check="v_f_disL(10) & trafficlight_color(3)"),
        "apollo/*.rule uses & to conjoin predicates; check is an implicit AND "
        "over whitespace-separated names only",
    ),
    "llm_self_examine": (
        rule(enforce="llm_self_examine"),
        "the README documents llm_self_examine; the grammar implements "
        "llm_self_reflect -- the docs and the language disagree",
    ),
}


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(src, marks=pytest.mark.xfail(strict=True, reason=why))
        for src, why in LIMITATIONS.values()
    ],
    ids=list(LIMITATIONS),
)
def test_known_grammar_limitation(source):
    """Currently fails. Flip to a plain assertion when S3.1 lands."""
    assert parse_errors(source) == []
