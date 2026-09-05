"""AgentSpec test bench — a local web UI for exercising rules against inputs.

Run:
    make ui          (or: .venv/bin/python ui/app.py)
    open http://127.0.0.1:5000

Local-only by design: it executes rule predicates and edits rule files, so it
binds to 127.0.0.1 and is never meant to face a network.
"""
import glob
import os
import sys

from flask import Flask, jsonify, render_template, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine                                          # noqa: E402
from examples import EXAMPLES                          # noqa: E402
from engine import REPO_ROOT, predicate_table          # noqa: E402

import agentguard                                      # noqa: E402

app = Flask(__name__)

# Rule files may only be read or written under these roots. The bench is
# local, but a path check costs nothing and stops a typo writing to src/.
RULE_ROOTS = [
    os.path.join(REPO_ROOT, "ui", "rules"),
    os.path.join(REPO_ROOT, "src", "rules"),
]


def _safe(rel):
    """Resolve a library-relative path, refusing anything outside RULE_ROOTS."""
    target = os.path.realpath(os.path.join(REPO_ROOT, rel))
    for root in RULE_ROOTS:
        if target == os.path.realpath(root) or target.startswith(
            os.path.realpath(root) + os.sep
        ):
            return target
    raise ValueError(f"path outside the rule library: {rel}")


def _library():
    """Every rule file the bench can open, newest scratch files first."""
    found = []
    for root in RULE_ROOTS:
        for pattern in ("**/*.ar", "**/*.rule"):
            for path in glob.glob(os.path.join(root, pattern), recursive=True):
                rel = os.path.relpath(path, REPO_ROOT)
                try:
                    text = open(path).read()
                except OSError:
                    continue
                found.append({
                    "path": rel,
                    "name": os.path.basename(path),
                    "scratch": rel.startswith("ui/"),
                    "rules": len(engine.split_rules(text)),
                    "bytes": len(text),
                })
    return sorted(found, key=lambda f: (not f["scratch"], f["path"]))


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/help")
def help_page():
    return render_template("help.html", examples=EXAMPLES,
                           predicates=sorted(predicate_table))


@app.get("/api/state")
def state():
    return jsonify({
        "library": _library(),
        "examples": EXAMPLES,
        "predicates": sorted(predicate_table),
        # Which engine the *run* goes through. The Cedar panel is shown either
        # way -- it decides the same call independently -- but with
        # AGENTGUARD=cedar the "Why - per rule" panel describes rules that no
        # longer decide anything, so the header has to say so.
        "engine": "cedar" if agentguard.enabled() else "legacy",
    })


@app.post("/api/parse")
def parse():
    text = request.json.get("text", "")
    return jsonify({"rules": [
        {k: v for k, v in entry.items() if k != "rule"}
        for entry in engine.load_rules(text)
    ]})


@app.post("/api/probe")
def probe():
    body = request.json
    return jsonify({"predicates": engine.probe_predicates(
        body.get("user_input", ""),
        body.get("tool_input", ""),
        body.get("intermediate_steps") or [],
    )})


@app.post("/api/run")
def run():
    body = request.json
    try:
        return jsonify(engine.run(
            body.get("rule_text", ""),
            body.get("user_input", ""),
            body.get("tool_name", "python_repl"),
            body.get("tool_input", ""),
            body.get("intermediate_steps") or [],
            approve=bool(body.get("approve", True)),
        ))
    except Exception as exc:                            # noqa: BLE001
        import traceback
        return jsonify({"verdict": "ERROR", "error": traceback.format_exc(),
                        "output": str(exc), "tool_calls": [], "steps": [],
                        "trace": "", "rules": [], "explain": [],
                        "cedar": engine.cedar_decision(
                            body.get("user_input", ""),
                            body.get("tool_name", "python_repl"),
                            body.get("tool_input", ""),
                            body.get("intermediate_steps") or [])}), 200


@app.get("/api/rule")
def read_rule():
    try:
        return jsonify({"text": open(_safe(request.args["path"])).read()})
    except (ValueError, OSError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/rule")
def write_rule():
    body = request.json
    try:
        path = _safe(body["path"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(body.get("text", ""))
    return jsonify({"saved": os.path.relpath(path, REPO_ROOT)})


if __name__ == "__main__":
    print("AgentSpec test bench -> http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
