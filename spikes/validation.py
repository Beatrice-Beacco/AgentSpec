#!/usr/bin/env python3
"""S1.3 -- what does validate_policies() catch before anything runs?

AgentSpec has no equivalent: a malformed or nonsensical rule is accepted at
load and only surfaces mid-run, if at all (tests/test_fail_open.py). This spike
establishes what Cedar catches at startup instead, which is the whole of RQ6.

It also settles a design question the plan left open (S2.2): should materialised
predicate results be a `Set<String>` of flag names, or a record of named Bools?
Only one of them lets the validator catch a misspelled flag.

    make spike-validation
"""
from cedarpy import Schema, validate_policies

ENTITIES = """
entity Agent = { framework: String };
entity Tool  = { kind: String, reversible: Bool };
"""

# Option A -- flags as an open set of strings. Flexible; any predicate name can
# appear without touching the schema.
SCHEMA_SET = ENTITIES + """
action invoke appliesTo {
  principal: [Agent],
  resource: [Tool],
  context: { flags: Set<String>, risk: Long }
};
"""

# Option B -- flags as a closed record of named Bools, generated from the
# predicate registry. Rigid; adding a predicate regenerates the schema.
SCHEMA_RECORD = ENTITIES + """
action invoke appliesTo {
  principal: [Agent],
  resource: [Tool],
  context: {
    flags: { involve_system_file: Bool, submit_post_request: Bool },
    risk: Long
  }
};
"""

INVOKE = 'Action::"invoke"'


def permit(condition, schema=SCHEMA_SET):
    return schema, f"permit(principal, action == {INVOKE}, resource) when {{ {condition} }};"


# (label, schema, policy, must_be_caught)
CASES = [
    ("valid policy", *permit("context.risk < 50"), False),
    ("typo in context attribute", *permit("context.rsik < 50"), True),
    ("typo in entity attribute", *permit('resource.kindd == "x"'), True),
    ("type mismatch (Long vs String)", *permit('context.risk == "high"'), True),
    ("unknown entity type", SCHEMA_SET,
     f'permit(principal, action == {INVOKE}, resource == Widget::"w");', True),
    ("unknown action", SCHEMA_SET,
     'permit(principal, action == Action::"delet", resource);', True),
    # The pair that decides S2.2. The Set<String> case is EXPECTED to be missed --
    # that is the finding, not a failure.
    ("misspelled flag - Set<String>",
     *permit('context.flags.contains("involve_system_fyle")'), False),
    ("misspelled flag - record of Bools",
     *permit("context.flags.involve_system_fyle", SCHEMA_RECORD), True),
]


def main():
    print(f"{'case':36s} {'caught?':9s} message")
    print("-" * 108)

    ok = True
    for label, schema, policy, must_be_caught in CASES:
        result = validate_policies(policy, Schema.from_str(schema))
        caught = not result.validation_passed
        verdict = "CAUGHT" if caught else ("valid" if label == "valid policy" else "MISSED")
        message = str(result.errors[0]).split("] ", 1)[-1][:60] if result.errors else "-"
        print(f"{label:36s} {verdict:9s} {message}")
        ok &= caught == must_be_caught

    print("""
Reading it:

  Five of the six malformed policies are caught before a single agent step runs.
  AgentSpec catches none of these -- there is no schema to check a rule against.

  The last two are the same typo under two schema designs, and they disagree:

    Set<String>       MISSED   any string is a valid set member, so a misspelled
                               predicate name is a policy that silently never fires
    record of Bools   CAUGHT   the attribute does not exist, and validation fails

  A silently-never-firing safety rule is the exact failure mode we are trying to
  leave behind (see tests/test_fail_open.py). So S2.2 should generate a
  record-of-Bools schema from the predicate registry, and accept the codegen step
  that comes with it. The plan recommended this; this is the evidence.""")

    print("S1.3:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
