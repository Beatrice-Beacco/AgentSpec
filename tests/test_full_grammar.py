"""The permissive grammar for reading the corpus (plan.md S3.1).

`agentguard/speclang/AgentSpecFull.g4` is a *second* grammar. The shipped one in
`src/spec_lang/` is deliberately untouched: it rejects 44 of the 62 rules in its
own repository, and that is a measurement worth keeping reproducible rather than
quietly repairing. Repairing it in place would also make "AgentSpec" in every
later experiment mean a version we had fixed.

So these tests assert three things:

  1. the full grammar accepts every construct the corpus actually uses;
  2. the shipped grammar still rejects them -- if that ever stops being true,
     someone has edited the baseline and the comparison is void;
  3. the corpus parse rate, pinned, so a grammar edit that loses coverage fails
     here rather than being discovered at S3.4.

Regenerating the parser needs Java and the ANTLR jar (both in the repo):

    java -jar src/spec_lang/antlr-4.13.2-complete.jar -Dlanguage=Python3 \
         -o agentguard/speclang agentguard/speclang/AgentSpecFull.g4
"""
import glob
import os
import re
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from antlr4 import CommonTokenStream, InputStream          # noqa: E402
from antlr4.error.ErrorListener import ErrorListener       # noqa: E402

from agentguard.speclang.AgentSpecFullLexer import AgentSpecFullLexer   # noqa: E402
from agentguard.speclang.AgentSpecFullParser import AgentSpecFullParser  # noqa: E402
from spec_lang.AgentSpecLexer import AgentSpecLexer        # noqa: E402
from spec_lang.AgentSpecParser import AgentSpecParser      # noqa: E402

SRC = os.path.join(REPO_ROOT, "src")


class _Collect(ErrorListener):
    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, sym, line, column, msg, e):
        self.errors.append(f"L{line}:{column} {msg}")


def parse(text, lexer_cls=AgentSpecFullLexer, parser_cls=AgentSpecFullParser):
    """Every lexer + parser error, with the default console listener removed."""
    lexer = lexer_cls(InputStream(text))
    lexer.removeErrorListeners()
    lex = _Collect()
    lexer.addErrorListener(lex)

    parser = parser_cls(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    par = _Collect()
    parser.addErrorListener(par)

    parser.program()
    return lex.errors + par.errors


def shipped(text):
    return parse(text, AgentSpecLexer, AgentSpecParser)


def rule(trigger="PythonREPL", check="involve_system_file", enforce="stop",
         prefix=""):
    return (f"{prefix}rule @r\ntrigger\n    {trigger}\n"
            f"check\n    {check}\nenforce\n    {enforce}\nend\n")


#: (label, source, does the shipped grammar reject it?)
CONSTRUCTS = [
    ("line comment", rule(prefix="// index 0\n"), True),
    ("block comment", rule(prefix="/* two\n   lines */\n"), True),
    ("capitalised True", rule(check="True"), True),
    ("unregistered predicate name", rule(check="is_malware"), True),
    ("dotted trigger", rule(trigger="Gmail.SendMail"), True),
    ("alternation", rule(trigger="Gmail.SendMail | Twilio.SendSms"), True),
    ("multi-word trigger", rule(trigger="turn on"), True),
    ("trigger any", rule(trigger="any"), True),
    ("llm_self_examine", rule(enforce="llm_self_examine"), True),
    ("enforcement with a message",
     rule(enforce='user_inspection("make sure it is reasonable")'), True),
    ("& between checks",
     rule(trigger="state_change", check="v_f_disL(10) & trafficlight_color(3)"), True),
    # These already worked; they must keep working.
    ("lowercase true", rule(check="true"), False),
    ("negation", rule(check="!involve_system_file"), False),
    ("registered predicate", rule(), False),
    ("invoke_action", rule(enforce='invoke_action(t, {"a": "b"})'), False),
    ("apollo config",
     rule(trigger="state_change", check="v_f_disL(10)",
          enforce="real:obstacle:Min_stop_distance = 10"), False),
]


# ------------------------------------------------------------- constructs

@pytest.mark.parametrize("label,source,_rejected", CONSTRUCTS,
                         ids=[c[0] for c in CONSTRUCTS])
def test_the_full_grammar_accepts_it(label, source, _rejected):
    assert parse(source) == [], label


@pytest.mark.parametrize(
    "label,source", [(c[0], c[1]) for c in CONSTRUCTS if c[2]],
    ids=[c[0] for c in CONSTRUCTS if c[2]])
def test_the_shipped_grammar_still_rejects_it(label, source):
    """The baseline must stay broken, or the comparison is void.

    If this starts failing, someone edited src/spec_lang/AgentSpec.g4 and every
    "AgentSpec cannot express this" claim needs rechecking.
    """
    assert shipped(source) != [], f"the shipped grammar now accepts {label!r}"


@pytest.mark.parametrize(
    "label,source", [(c[0], c[1]) for c in CONSTRUCTS if not c[2]],
    ids=[c[0] for c in CONSTRUCTS if not c[2]])
def test_the_full_grammar_is_a_superset(label, source):
    """Anything the shipped grammar accepts, the full one accepts too."""
    assert shipped(source) == [], f"fixture {label!r} is not shipped-legal"
    assert parse(source) == []


# ----------------------------------------------------------- the corpus

def corpus_rules():
    """Every rule in the shipped corpus, split the way a compiler sees it."""
    files = sorted(glob.glob(os.path.join(SRC, "rules/**/*.ar"), recursive=True))
    files += sorted(glob.glob(os.path.join(SRC, "rules/**/*.rule"), recursive=True))
    out = []
    for path in files:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        for chunk in re.sub(r"//.*", "", text).split("rule @")[1:]:
            chunk = "rule @" + chunk
            if "\nend" in chunk:
                chunk = chunk[:chunk.index("\nend") + 4]
            name = re.search(r"rule @(\w+)", chunk)
            out.append((os.path.basename(path), name.group(1) if name else "?", chunk))
    return out


def test_the_corpus_is_the_size_we_think_it_is():
    assert len(corpus_rules()) == 62


def test_the_full_grammar_reads_all_but_one_corpus_rule():
    """S3.1's acceptance, and the ceiling on S3.4's coverage.

    The one exception is not a grammar gap. `@inspect_side_channel` in
    pythonrepl.ar has an English sentence where its check clause should be:

        resources_that_provide_side_channel_info(e.g. how much time/power ...)

    Accepting that would mean accepting arbitrary prose, so it stays rejected
    and is reported as a rule that was never written in the language.
    """
    failed = [(f, name) for f, name, text in corpus_rules() if parse(text)]

    assert failed == [("pythonrepl.ar", "inspect_side_channel")], failed


def test_the_shipped_grammar_reads_only_a_quarter_of_it():
    """The baseline measurement this whole step exists to preserve."""
    ok = sum(1 for _f, _n, text in corpus_rules() if not shipped(text))

    assert ok == 18, f"the shipped grammar now parses {ok}/62; was 18"


def test_the_full_grammar_is_a_strict_improvement_on_every_rule():
    """No rule may parse under the shipped grammar and fail under ours."""
    regressions = [name for _f, name, text in corpus_rules()
                   if not shipped(text) and parse(text)]

    assert regressions == []


# ------------------------------------------------------ the generated parser

def test_the_generated_parser_matches_the_grammar_file():
    """A stale checked-in parser would make every test above meaningless.

    Cheap proxy for regenerating: the header ANTLR writes names the grammar, and
    the token set has to contain the tokens the .g4 declares.
    """
    generated = os.path.join(REPO_ROOT, "agentguard", "speclang",
                             "AgentSpecFullParser.py")
    with open(generated, encoding="utf-8") as handle:
        header = handle.readline()
    assert "AgentSpecFull.g4" in header

    with open(os.path.join(REPO_ROOT, "agentguard", "speclang",
                           "AgentSpecFull.tokens"), encoding="utf-8") as handle:
        tokens = handle.read()
    for token in ("AND", "OR", "LINE_COMMENT", "BLOCK_COMMENT"):
        assert f"{token}=" in tokens, f"{token} missing -- regenerate the parser"
