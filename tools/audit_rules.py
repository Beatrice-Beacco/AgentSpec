#!/usr/bin/env python3
"""Audit the AgentSpec rule corpus against AgentSpec's own generated ANTLR parser.

Produces the evidence tables in Part B of AgentSpec-Cedar-Thesis-Plan.md.

Usage:
    pip install "antlr4-python3-runtime==4.13" pydantic
    python tools/audit_rules.py /path/to/AgentSpec/src
"""
import sys, os, re, glob, subprocess, datetime

SRC = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "AgentSpec/src")
sys.path.insert(0, SRC)

from antlr4 import InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener
from spec_lang.AgentSpecLexer import AgentSpecLexer
from spec_lang.AgentSpecParser import AgentSpecParser


class Collect(ErrorListener):
    def __init__(self):
        self.errs = []

    def syntaxError(self, recognizer, sym, line, col, msg, e):
        self.errs.append(f"L{line}:{col} {msg}")


def parse(text):
    """Parse rule text; return the list of lexer+parser syntax errors."""
    lexer = AgentSpecLexer(InputStream(text))
    lexer.removeErrorListeners()
    lex_errs = Collect()
    lexer.addErrorListener(lex_errs)

    parser = AgentSpecParser(CommonTokenStream(lexer))
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
        rel = os.path.relpath(f, SRC)
        text = open(f).read()
        if not text.strip():
            print(f"| {rel:45s} | empty |")
            continue
        errs = parse(text)
        result = "OK" if not errs else f"**{len(errs)} errors** — {errs[0]}"
        print(f"| {rel:45s} | {result} |")


def audit_rules():
    print("\n## B.1b  Per-rule parse (comments stripped, split on `rule @`)\n")
    print(f"| {'File':45s} | Rules | OK | FAIL |")
    print(f"|{'-'*47}|------:|---:|-----:|")
    for f in sorted(glob.glob(os.path.join(SRC, "rules/**/*.ar"), recursive=True)):
        text = open(f).read()
        if not text.strip():
            continue
        chunks = ["rule @" + c for c in re.sub(r"//.*", "", text).split("rule @")[1:]]
        ok = sum(1 for c in chunks if not parse(c))
        print(f"| {os.path.relpath(f, SRC):45s} | {len(chunks):5d} | {ok:2d} | {len(chunks)-ok:4d} |")


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
    dirty = git("status", "--porcelain") not in ("", "unknown")

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
        f"| commit | `{sha}`{' **(working tree dirty)**' if dirty else ''} |",
        f"| branch | `{branch}` |",
        f"| source tree | `{os.path.relpath(SRC, repo)}` |",
        f"| python | {sys.version.split()[0]} |",
        f"| antlr4 runtime | {antlr} |",
        "",
        "Every table below is produced by parsing the shipped rule files with the",
        "repo's own generated lexer and parser — the same classes `Rule.from_text`",
        "uses at runtime. Nothing here is hand-counted.",
        "",
    ])


if __name__ == "__main__":
    print(provenance())
    audit_files()
    audit_rules()
    audit_features()
    audit_fail_open()
