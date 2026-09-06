#!/usr/bin/env python3
"""Validate the Cedar policy files against policies/schema.cedarschema.

This is the load-time check AgentSpec does not have. `tests/test_fail_open.py`
documents four ways a malformed AgentSpec rule gets past loading -- silent
acceptance, silent truncation, an internal crash, and an unregistered predicate.
Every one of them is a rule that looks loaded and is not. Cedar's validator
turns the equivalent mistakes into an error before the agent takes a step
(docs/spikes.md S1.3), and this script is where that happens for our own files.

Usage:

    python tools/validate_policies.py                  # every policies/**/*.cedar
    python tools/validate_policies.py policies/core.cedar

Exit code is 0 only if the schema parses and every policy file validates, so it
works as a CI gate and as the precondition for S2.5's "refuse to start".
"""
import argparse
import glob
import json
import os
import sys

try:
    from cedarpy import Schema, policies_to_json_str, validate_policies
except ImportError:                                     # pragma: no cover
    sys.exit("cedarpy is not installed -- pip install -r requirements-dev.txt")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY_DIR = os.path.join(REPO_ROOT, "policies")
SCHEMA_PATH = os.path.join(POLICY_DIR, "schema.cedarschema")

# The enforcement outcomes @advice may name, most restrictive first (thesis
# §C.4). Cedar validates policy *logic* against the schema but treats every
# annotation as an opaque string, so nothing but this check stands between a
# typo'd @advice("stopp") and a crash in the resolver at decision time -- the
# same shape of silent failure tests/test_fail_open.py records for AgentSpec.
#
# S2.4 gives the lattice a real home in agentguard/advice.py; import it from
# there when it exists rather than keeping two copies.
ADVICE_LATTICE = ["stop", "user_inspection", "llm_self_reflect", "skip", "allow"]


def _schema_is_current(path):
    """(ok, reason) -- is the schema still what agentguard/schema.py generates?

    Soft-imported: the validator's core job is checking policy files, and it
    should keep doing that on a checkout where `agentguard` cannot be imported.
    """
    try:
        sys.path.insert(0, REPO_ROOT)
        from agentguard import schema as ag_schema      # noqa: PLC0415
    except ImportError:                                 # pragma: no cover
        return True, ""
    return ag_schema.is_current(path)


def load_schema(path=SCHEMA_PATH):
    """Parse the schema, or raise with the file's own error text."""
    with open(path, encoding="utf-8") as fh:
        return Schema.from_str(fh.read())


def policy_files(paths=None):
    """The .cedar files to check: the arguments, or the whole policy tree."""
    if paths:
        return [os.path.abspath(p) for p in paths]
    return sorted(glob.glob(os.path.join(POLICY_DIR, "**", "*.cedar"), recursive=True))


def annotation_errors(text):
    """Lint the annotations Cedar itself will not check.

    Three rules, all about traceability of an enforcement outcome:

      * every policy carries @id -- diagnostics.reasons returns synthetic ids
        ("policy0", "policy1"), so without @id a decision cannot be attributed
        to anything a human wrote;
      * @advice, where present, names a real lattice element;
      * @advice does not appear on a permit, where it would be silently
        ignored (thesis §C.4 rule 1: an Allow resolves to `allow`).

    An unannotated `forbid` is allowed: it defaults to `stop`, the safe end of
    the lattice (docs/spikes.md S1.2). A typo'd one is not, because it would
    reach the resolver and fail there instead.
    """
    parsed = json.loads(policies_to_json_str(text))
    errors = []
    for pid, body in sorted(parsed.get("staticPolicies", {}).items()):
        anns = body.get("annotations", {})
        name = anns.get("id", pid)
        if "id" not in anns:
            errors.append(f"{pid}: no @id -- the decision cannot be traced to a rule")
        advice = anns.get("advice")
        if advice is not None and advice not in ADVICE_LATTICE:
            errors.append(
                f"{name}: @advice(\"{advice}\") is not an enforcement outcome "
                f"(expected one of {', '.join(ADVICE_LATTICE)})"
            )
        if advice is not None and body.get("effect") == "permit":
            errors.append(
                f"{name}: @advice on a permit has no effect -- advice is only "
                "read off denying policies"
            )
    return errors


def check(path, schema):
    """(ok, [message]) for one policy file."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    result = validate_policies(text, schema)
    if not result.validation_passed:
        # Cedar prefixes errors with a bracketed severity; keep the useful half.
        return False, [str(e).split("] ", 1)[-1] for e in result.errors]
    errors = annotation_errors(text)
    return not errors, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="policy files (default: policies/**/*.cedar)")
    parser.add_argument("--schema", default=SCHEMA_PATH)
    args = parser.parse_args(argv)

    rel = lambda p: os.path.relpath(p, REPO_ROOT).replace(os.sep, "/")  # noqa: E731

    try:
        schema = load_schema(args.schema)
    except Exception as exc:                            # noqa: BLE001
        print(f"FAIL  {rel(args.schema)}\n      {exc}")
        return 1

    # The schema is generated from the sensor registry (S2.2), so "it parses" is
    # not enough -- it also has to still be what the registry says. A
    # hand-edited or stale schema type-checks perfectly and silently omits a
    # flag, which is a policy that can never fire.
    current, reason = _schema_is_current(args.schema)
    if not current:
        print(f"FAIL  {rel(args.schema)}\n      {reason}")
        return 1
    print(f"ok    {rel(args.schema)}  (parses, and matches the sensor registry)")

    files = policy_files(args.paths)
    if not files:
        print("      no .cedar policy files yet -- policies/core.cedar arrives in S1.6")
        return 0

    failed = 0
    for path in files:
        ok, messages = check(path, schema)
        print(f"{'ok  ' if ok else 'FAIL'}  {rel(path)}")
        for message in messages:
            print(f"      {message}")
        failed += not ok

    print(f"\n{len(files) - failed}/{len(files)} policy files valid")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
