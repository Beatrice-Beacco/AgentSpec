"""RQ6: does the Cedar engine fail closed where AgentSpec fails open? (plan.md S2.5)

The paired file to `tests/test_fail_open.py`, which records the four ways an
AgentSpec rule loads cleanly and then does the wrong thing. Each of those four
has a counterpart here, run against `agentguard.engine.load()`.

**Why the S0.12 xfails are still xfails.** The plan's acceptance for S2.5 reads
"S0.12's xfail test now passes -- flip it from xfail to a real assertion". Those
tests assert on `Rule.from_text`, i.e. on AgentSpec's own loader, and building a
Cedar engine does not change it. The only way to make them pass is to patch
`src/rule.py` -- and then every comparison in the thesis would be against a
baseline we had repaired, not against AgentSpec. So they stay red-by-design as
the record of the baseline, and RQ6 is answered here instead: the same four
mistakes, in the new engine, are load-time errors that stop the agent starting.

    mode                       AgentSpec                     AgentGuard
    -------------------------- ----------------------------- -----------------
    1 malformed source         accepted; ValueError mid-run  refused at load
    2 silent truncation        `Gmail.SendMail` -> `Gmail`   no truncation
    3 comment breaks the parse depends on the word count     comments are fine
    4 unknown predicate name   accepted; KeyError mid-run    refused at load

Mode 4 is the interesting one, and it is *not* free -- see
`test_a_guarded_typo_passes_cedars_own_validator`. Cedar's validator does not
catch it, because the guard idiom S2.2 requires defeats the check S2.2 added.
The engine's coverage check is what closes it.
"""
import os
import sys

import pytest

cedarpy = pytest.importorskip("cedarpy")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from agentguard import engine                      # noqa: E402
from agentguard import schema as ag_schema         # noqa: E402
from agentguard import sensors                     # noqa: E402

INVOKE = 'AgentGuard::Action::"invoke"'
GOOD = (f'@id("baseline") permit (principal, action == {INVOKE}, resource);\n'
        f'@id("guard") @advice("stop") forbid (principal, action == {INVOKE}, '
        'resource) when { context.flags has destuctive_os_inst && '
        'context.flags.destuctive_os_inst };')


@pytest.fixture
def policy_dir(tmp_path):
    """A policy directory with the real generated schema and nothing else."""
    (tmp_path / "schema.cedarschema").write_text(ag_schema.generate(),
                                                 encoding="utf-8")

    def write(policy_text, name="p.cedar"):
        (tmp_path / name).write_text(policy_text, encoding="utf-8")
        engine.load.cache_clear()
        return str(tmp_path)

    return write


def refuses(directory):
    """Load and return the PolicyError message, or fail if it loaded."""
    with pytest.raises(engine.PolicyError) as exc:
        engine.load(directory)
    return str(exc.value)


def loads(directory):
    return engine.load(directory)


# ------------------------------------------------------ 1. malformed source

@pytest.mark.parametrize("label,policy", [
    ("missing semicolon", f'@id("p") forbid (principal, action == {INVOKE}, resource)'),
    ("not cedar at all", "this is not a policy"),
    ("unclosed brace",
     f'@id("p") forbid (principal, action == {INVOKE}, resource) when {{ '),
    ("unknown attribute",
     f'@id("p") forbid (principal, action == {INVOKE}, resource) '
     'when { context.flgs.contains("x") };'),
])
def test_malformed_policy_is_refused_at_load(label, policy, policy_dir):
    """AgentSpec's mode 1: accepted at load, ValueError mid-run."""
    assert "does not validate" in refuses(policy_dir(policy)), label


def test_a_refusal_says_what_is_wrong():
    """An engine that refuses to start only beats one that fails open if the
    refusal is actionable."""
    import tempfile                                # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "schema.cedarschema"), "w",
                  encoding="utf-8") as handle:
            handle.write(ag_schema.generate())
        with open(os.path.join(tmp, "p.cedar"), "w", encoding="utf-8") as handle:
            handle.write(f'@id("p") forbid (principal, action == {INVOKE}, '
                         'resource) when { context.flgs.contains("x") };')
        engine.load.cache_clear()
        message = refuses(tmp)

    assert "flgs" in message


# ----------------------------------------------------- 2. silent truncation

def test_a_dotted_tool_name_is_not_truncated(policy_dir):
    """AgentSpec's mode 2, the most dangerous of the four.

    `trigger Gmail.SendMail` loads as event `Gmail`, so the rule arms on a
    different tool than written. In Cedar the tool is a quoted entity uid, so
    there is nothing to truncate -- the policy matches that tool and no other.
    """
    policy = (f'@id("baseline") permit (principal, action == {INVOKE}, resource);\n'
              f'@id("guard") @advice("stop") forbid (principal, action == {INVOKE}, '
              'resource == AgentGuard::Tool::"Gmail.SendMail");')
    bundle = loads(policy_dir(policy))

    def decide(tool):
        return cedarpy.is_authorized({
            "principal": 'AgentGuard::Agent::"a"', "action": INVOKE,
            "resource": f'AgentGuard::Tool::"{tool}"', "context": {"flags": {}},
        }, bundle.policy_set, [], bundle.schema).decision

    assert decide("Gmail.SendMail") == cedarpy.Decision.Deny
    assert decide("Gmail") == cedarpy.Decision.Allow, "truncated to the wrong tool"


# --------------------------------------------------------- 3. comments

@pytest.mark.parametrize("comment", [
    "//index1",
    "// index 0",
    "// a comment with a good many words in it",
    "//",
], ids=["one-token", "two-tokens", "many-tokens", "empty"])
def test_comments_do_not_change_whether_a_policy_loads(comment, policy_dir):
    """AgentSpec's mode 3, which is genuinely absurd.

    Its grammar has no comment token, so `// index 0` (two tokens) breaks ANTLR
    recovery hard enough that Rule.from_text dies with AttributeError, while
    `//index1` (one token) is accepted. Identical-looking comments behave
    differently by word count. Cedar has comments.
    """
    bundle = loads(policy_dir(f"{comment}\n{GOOD}"))
    assert len(bundle.annotations) == 2


# ------------------------------------------------- 4. unknown predicate name

def test_a_flag_no_sensor_produces_is_refused_at_load(policy_dir):
    """AgentSpec's mode 4: `is_malware` is defined in Python, never registered,
    and a rule naming it raises KeyError mid-run."""
    policy = (f'@id("baseline") permit (principal, action == {INVOKE}, resource);\n'
              f'@id("guard") @advice("stop") forbid (principal, action == {INVOKE}, '
              'resource) when { context.flags has is_malware && '
              'context.flags.is_malware };')
    message = refuses(policy_dir(policy))

    assert "can never fire" in message
    assert "is_malware" in message
    assert "misspelled" in message


def test_a_flag_from_another_domain_is_refused_at_load(policy_dir):
    """The same check, for a flag that exists but this engine will never run.

    Cedar cannot see this at all: `is_candle` is a perfectly good attribute of
    the schema, which declares all 36 registered sensors. Only the engine knows
    it runs the code domain and so will never materialise an embodied flag.
    """
    policy = (f'@id("baseline") permit (principal, action == {INVOKE}, resource);\n'
              f'@id("guard") @advice("stop") forbid (principal, action == {INVOKE}, '
              'resource) when { context.flags has is_candle && '
              'context.flags.is_candle };')
    message = refuses(policy_dir(policy))

    assert "can never fire" in message
    assert "domain embodied" in message
    assert sensors.get("is_candle").domain == sensors.EMBODIED


def test_a_guarded_typo_passes_cedars_own_validator():
    """Why the coverage check is load-bearing rather than a nicety.

    S2.2 closed the misspelled-flag hole by making `flags` a record -- but only
    for an *unguarded* access, and Cedar refuses to validate those. The guarded
    form, which is the only one it accepts for an optional attribute, type-checks
    with any name at all: asking whether a record has an attribute is legitimate
    even when it statically cannot.

    So the idiom S2.2 mandates defeats the check S2.2 added, and the engine's
    coverage check is the only thing standing between a typo and a safety policy
    that silently never fires.
    """
    guarded = (f'permit (principal, action == {INVOKE}, resource) when '
               '{ context.flags has destuctive_os_inzt && '
               'context.flags.destuctive_os_inzt };')
    schema = cedarpy.Schema.from_str(ag_schema.generate())

    assert cedarpy.validate_policies(guarded, schema).validation_passed


def test_and_the_engine_refuses_it(policy_dir):
    policy = (f'@id("baseline") permit (principal, action == {INVOKE}, resource);\n'
              f'@id("guard") @advice("stop") forbid (principal, action == {INVOKE}, '
              'resource) when { context.flags has destuctive_os_inzt && '
              'context.flags.destuctive_os_inzt };')
    assert "destuctive_os_inzt" in refuses(policy_dir(policy))


# ------------------------------------------------ beyond the four modes

def test_an_unrecognised_advice_value_is_refused_at_load(policy_dir):
    """The engine now enforces the lint the CLI had. Until S2.5 a policy set
    that skipped `make validate` could load with a typo'd @advice."""
    policy = (f'@id("p") @advice("stopp") forbid (principal, action == {INVOKE}, '
              'resource);')
    assert "not an enforcement outcome" in refuses(policy_dir(policy))


def test_a_policy_without_an_id_is_refused_at_load(policy_dir):
    assert "no @id" in refuses(policy_dir(
        f'forbid (principal, action == {INVOKE}, resource);'))


def test_an_empty_policy_directory_is_refused(tmp_path):
    (tmp_path / "schema.cedarschema").write_text(ag_schema.generate(),
                                                 encoding="utf-8")
    engine.load.cache_clear()
    message = refuses(str(tmp_path))

    assert "no .cedar policy files" in message
    assert "allow everything" in message


def test_a_missing_schema_is_refused(tmp_path):
    (tmp_path / "p.cedar").write_text(GOOD, encoding="utf-8")
    engine.load.cache_clear()
    assert "make schema" in refuses(str(tmp_path))


def test_the_shipped_policy_set_loads():
    """The checks are only meaningful if the real policy set passes them."""
    engine.load.cache_clear()
    bundle = engine.load()

    assert bundle.flags_read
    assert all(bundle.name_for(pid) for pid in bundle.annotations)


def test_a_refused_policy_set_stops_the_agent_being_built(tmp_path, monkeypatch):
    """Refusing to load is only useful if it actually prevents a run."""
    import agentguard                              # noqa: PLC0415
    from agentguard import executor                # noqa: PLC0415

    (tmp_path / "schema.cedarschema").write_text(ag_schema.generate(),
                                                 encoding="utf-8")
    (tmp_path / "p.cedar").write_text(
        f'@id("p") @advice("stopp") forbid (principal, action == {INVOKE}, '
        'resource);', encoding="utf-8")
    monkeypatch.setattr(agentguard, "POLICY_DIR", str(tmp_path))
    engine.load.cache_clear()

    with pytest.raises(engine.PolicyError):
        executor.CedarControlledAgentExecutor.from_agent_and_tools(
            agent=None, tools=[], rules=[])
    engine.load.cache_clear()
