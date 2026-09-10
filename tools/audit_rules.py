#!/usr/bin/env python3
"""Audit the AgentSpec rule corpus against AgentSpec's own generated ANTLR parser.

Produces the evidence tables in Part B of AgentSpec-Cedar-Thesis-Plan.md.

Two grammars can be used, and the difference between them is the point:

    --grammar shipped   src/spec_lang/AgentSpec.g4, exactly as AgentSpec ships
                        it. Rejects 21 of the 42 rules in its own repository.
    --grammar full      agentguard/speclang/AgentSpecFull.g4, the permissive
                        grammar our compiler reads the corpus with (S3.1).

The shipped grammar is deliberately never modified: what it rejects is a
measurement, and repairing it in place would turn that measurement into history.

Usage:
    python tools/audit_rules.py src
    python tools/audit_rules.py src --grammar full
"""
import sys, os, re, glob, subprocess, datetime, argparse

_parser = argparse.ArgumentParser(description="audit the AgentSpec rule corpus")
_parser.add_argument("src", nargs="?", default="AgentSpec/src")
_parser.add_argument("--grammar", choices=("shipped", "full"), default="shipped")
_args = _parser.parse_args()

SRC = os.path.abspath(_args.src)
GRAMMAR = _args.grammar
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
sys.path.insert(0, REPO)

from antlr4 import InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener

if GRAMMAR == "full":
    from agentguard.speclang.AgentSpecFullLexer import AgentSpecFullLexer as Lexer
    from agentguard.speclang.AgentSpecFullParser import AgentSpecFullParser as Parser
    GRAMMAR_PATH = "agentguard/speclang/AgentSpecFull.g4"
else:
    from spec_lang.AgentSpecLexer import AgentSpecLexer as Lexer
    from spec_lang.AgentSpecParser import AgentSpecParser as Parser
    GRAMMAR_PATH = "src/spec_lang/AgentSpec.g4"


class Collect(ErrorListener):
    def __init__(self):
        self.errs = []

    def syntaxError(self, recognizer, sym, line, col, msg, e):
        self.errs.append(f"L{line}:{col} {msg}")


def parse(text):
    """Parse rule text; return the list of lexer+parser syntax errors."""
    lexer = Lexer(InputStream(text))
    lexer.removeErrorListeners()
    lex_errs = Collect()
    lexer.addErrorListener(lex_errs)

    parser = Parser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parse_errs = Collect()
    parser.addErrorListener(parse_errs)

    parser.program()
    return lex_errs.errs + parse_errs.errs


def audit_files():
    print("## B.1  Whole-file parse\n")
    print(f"| {'Rule file':45s} | Result |")
    print(f"|{'-'*47}|--------|")
    files = sorted(glob.glob(os.path.join(SRC, "rules/**/*.ar"), recursive=True))
    files += sorted(glob.glob(os.path.join(SRC, "rules/**/*.rule"), recursive=True))
    for f in files:
        rel = os.path.relpath(f, SRC).replace(os.sep, "/")
        text = open(f, encoding="utf-8", errors="replace").read()
        if not text.strip():
            print(f"| {rel:45s} | empty |")
            continue
        errs = parse(text)
        result = "OK" if not errs else f"**{len(errs)} errors** — {errs[0]}"
        print(f"| {rel:45s} | {result} |")


def rule_chunks(text):
    """Split a rule file into individual rules, the way a compiler sees it.

    Trimming at each rule's own `end` matters: two corpus files carry unmarked
    prose between rules (`=== below is security-related` in pythonrepl.ar,
    `case 20-23 The23andMe ????` in toolemu.ar). It is neither comment nor rule,
    so without the trim it is charged to whichever rule precedes it.
    """
    chunks = ["rule @" + c for c in re.sub(r"//.*", "", text).split("rule @")[1:]]
    return [c[:c.index("\nend") + 4] if "\nend" in c else c for c in chunks]


def audit_rules():
    """Per-rule parse -- what a compiler actually consumes.

    Whole-file parsing (B.1) is stricter and can never reach zero while the
    stray prose above is in the files. Splitting on `rule @` is how S3.3 reads
    the corpus, so this is the number that bounds compiler coverage.
    """
    print("\n## B.1b  Per-rule parse (comments stripped, split on `rule @`)\n")
    print(f"| {'File':45s} | Rules | OK | FAIL |")
    print(f"|{'-'*47}|------:|---:|-----:|")
    files = sorted(glob.glob(os.path.join(SRC, "rules/**/*.ar"), recursive=True))
    files += sorted(glob.glob(os.path.join(SRC, "rules/**/*.rule"), recursive=True))
    total = total_ok = 0
    for f in files:
        text = open(f, encoding="utf-8", errors="replace").read()
        if not text.strip():
            continue
        chunks = rule_chunks(text)
        if not chunks:
            continue
        ok = sum(1 for c in chunks if not parse(c))
        total += len(chunks)
        total_ok += ok
        rel = os.path.relpath(f, SRC).replace(os.sep, "/")
        print(f"| {rel:45s} | {len(chunks):5d} | {ok:2d} | {len(chunks)-ok:4d} |")
    print(f"| {'**total**':45s} | **{total}** | **{total_ok}** | **{total-total_ok}** |")


PROBES = {
    "baseline (grammar-legal)":     "rule @r\ntrigger\n PythonREPL\ncheck\n involve_system_file\nenforce\n stop\nend\n",
    "comment line //":              "//index1\nrule @r\ntrigger\n PythonREPL\ncheck\n involve_system_file\nenforce\n stop\nend\n",
    "predicate not in token list":  "rule @r\ntrigger\n PythonREPL\ncheck\n is_malware\nenforce\n stop\nend\n",
    "capitalised True":             "rule @r\ntrigger\n PythonREPL\ncheck\n True\nenforce\n stop\nend\n",
    "lowercase true":               "rule @r\ntrigger\n PythonREPL\ncheck\n true\nenforce\n stop\nend\n",
    "trigger alternation A|B":      "rule @r\ntrigger\n Gmail.SendMail | Twilio.SendSms\ncheck\n true\nenforce\n stop\nend\n",
    "dotted trigger":               "rule @r\ntrigger\n Gmail.SendMail\ncheck\n true\nenforce\n stop\nend\n",
    "multiword trigger":            "rule @r\ntrigger\n turn on\ncheck\n true\nenforce\n stop\nend\n",
    "llm_self_examine (README)":    "rule @r\ntrigger\n PythonREPL\ncheck\n true\nenforce\n llm_self_examine\nend\n",
    "llm_self_reflect (grammar)":   "rule @r\ntrigger\n PythonREPL\ncheck\n true\nenforce\n llm_self_reflect\nend\n",
    "invoke_action":                'rule @r\ntrigger\n PythonREPL\ncheck\n true\nenforce\n invoke_action(t, {"a": "b"})\nend\n',
    "conjunction with &":           "rule @r\ntrigger\n state_change\ncheck\n v_f_disL(10) & trafficlight_color(3)\nenforce\n stop\nend\n",
    "negation !p":                  "rule @r\ntrigger\n PythonREPL\ncheck\n !involve_system_file\nenforce\n stop\nend\n",
}


def audit_features():
    print("\n## B.2  Language-feature probes\n")
    print(f"| {'Construct':32s} | Parses? |")
    print(f"|{'-'*34}|---------|")
    for name, src in PROBES.items():
        errs = parse(src)
        print(f"| {name:32s} | {'yes' if not errs else 'NO — ' + errs[0]} |")


def audit_fail_open():
    """B.3: Rule.from_text installs no error listener -> malformed rules construct fine."""
    print("\n## B.3  Fail-open check (`Rule.from_text` on malformed input)\n")
    try:
        from rule import Rule
    except Exception as e:
        print(f"(skipped: could not import rule.py — {e})")
        return
    for name in ("predicate not in token list", "llm_self_examine (README)"):
        try:
            r = Rule.from_text(PROBES[name])
            print(f"- `{name}` -> **constructed anyway**: id={r.id!r} event={r.event!r}")
        except Exception as e:
            print(f"- `{name}` -> raised {type(e).__name__}: {e}")


def provenance():
    """Header identifying exactly what was audited, so the output is citable.

    A frozen copy of this report is thesis evidence (plan.md S0.10); without
    the commit it was generated from, it is just a table of numbers.
    """
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def git(*args):
        try:
            return subprocess.run(("git", "-C", repo) + args, capture_output=True,
                                  text=True, check=True).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    sha, branch = git("rev-parse", "HEAD"), git("rev-parse", "--abbrev-ref", "HEAD")
    # Only the audited tree matters for provenance. A plain `git status` would
    # flag this report itself, since it is written while the check runs.
    dirty = git("status", "--porcelain", "--untracked-files=no", "--",
                os.path.relpath(SRC, repo)) not in ("", "unknown")

    try:
        import antlr4                                   # noqa: PLC0415
        antlr = getattr(antlr4, "__version__", "installed")
    except ImportError:
        antlr = "missing"

    return "\n".join([
        "# AgentSpec rule-corpus audit",
        "",
        "> Generated by `tools/audit_rules.py`. Regenerate with `make audit-freeze`.",
        "",
        "| | |",
        "|---|---|",
        f"| generated | {datetime.date.today().isoformat()} |",
        f"| commit | `{sha}`{' **(audited tree has uncommitted changes)**' if dirty else ''} |",
        f"| branch | `{branch}` |",
        f"| source tree | `{os.path.relpath(SRC, repo)}` (clean at this commit) |" if not dirty
        else f"| source tree | `{os.path.relpath(SRC, repo)}` |",
        f"| grammar | `{GRAMMAR_PATH}` (`--grammar {GRAMMAR}`) |",
        f"| python | {sys.version.split()[0]} |",
        f"| antlr4 runtime | {antlr} |",
        "",
        "Every table below is produced by parsing the shipped rule files with a",
        "generated ANTLR lexer and parser. Nothing here is hand-counted.",
        "",
        ("The **shipped** grammar is the one `Rule.from_text` uses at runtime —\n"
         "this is AgentSpec exactly as published."
         if GRAMMAR == "shipped" else
         "The **full** grammar is ours (S3.1), used only to read the corpus for\n"
         "compilation. The shipped grammar is left untouched; read this report\n"
         "against `docs/baseline-audit.md`."),
        "",
    ])


if __name__ == "__main__":
    print(provenance())
    audit_files()
    audit_rules()
    audit_features()
    audit_fail_open()
