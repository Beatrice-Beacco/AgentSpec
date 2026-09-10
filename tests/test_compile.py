"""AgentSpec rule -> Cedar policy (plan.md S3.3, thesis §C.6).

S3.3's acceptance is *"compiling the smoke-test rule yields a policy that
produces an identical verdict"* -- so the headline test does not compare policy
text, it runs both through the engine and compares what the agent would do.
Text equality would be the wrong assertion: two policies can be spelled
differently and decide the same, which is the only thing that matters.

The rest covers the §C.6 mapping row by row, and the reasons a rule cannot be
compiled -- which are the RQ1 material S3.5 turns into `docs/coverage.md`.
"""
import glob
import json
import os
import shutil
import sys
import tempfile

import pytest

cedarpy = pytest.importorskip("cedarpy")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from agentguard import compile as ag_compile      # noqa: E402
from agentguard import engine                     # noqa: E402
from agentguard import schema as ag_schema        # noqa: E402
from agentguard import sensors                    # noqa: E402

BASELINE = ('@id("baseline_allow_tools")\n'
            'permit (principal, action == AgentGuard::Action::"invoke", resource);\n')

SMOKE_RULE = """rule @block_file_deletion
trigger
    python_repl
check
    destuctive_os_inst
enforce
    stop
end
"""


def compile_one(text, source="agentspec:test"):
    results = ag_compile.compile_text(text, source)
    assert len(results) == 1, results
    return results[0]


def rule(trigger="python_repl", check="destuctive_os_inst", enforce="stop",
         name="r"):
    return (f"rule @{name}\ntrigger\n    {trigger}\n"
            f"check\n    {check}\nenforce\n    {enforce}\nend\n")


@pytest.fixture
def policy_dir():
    """A policy directory holding the baseline permit plus whatever is compiled."""
    made = []

    def build(policy_text):
        tmp = tempfile.mkdtemp()
        made.append(tmp)
        with open(os.path.join(tmp, "schema.cedarschema"), "w",
                  encoding="utf-8") as handle:
            handle.write(ag_schema.generate())
        with open(os.path.join(tmp, "core.cedar"), "w", encoding="utf-8") as handle:
            handle.write(BASELINE + "\n" + policy_text)
        engine.load.cache_clear()
        return tmp

    yield build
    engine.load.cache_clear()
    for tmp in made:
        shutil.rmtree(tmp, ignore_errors=True)


def state(tool_input, tool="python_repl"):
    from langchain_core.agents import AgentAction          # noqa: PLC0415

    from agent import Action                               # noqa: PLC0415
    from state import RuleState                            # noqa: PLC0415

    action = Action.from_langchain(
        AgentAction(tool=tool, tool_input=tool_input, log=""))
    return RuleState(action=action, agent=None, intermediate_steps=[],
                     user_input="Delete the unimportant txt file")


# ---------------------------------------------------------- S3.3 acceptance

DESTRUCTIVE = 'import os; os.remove("notes.txt")'
BENIGN = "print(6 * 7)"


def test_the_smoke_test_rule_compiles(policy_dir):
    compiled = compile_one(SMOKE_RULE, "agentspec:tests/test_enforcement.py")

    assert compiled.ok, compiled.reason
    assert '@id("block_file_deletion")' in compiled.policy
    assert '@advice("stop")' in compiled.policy
    assert 'resource == AgentGuard::Tool::"python_repl"' in compiled.policy
    assert "context.flags has destuctive_os_inst" in compiled.policy
    # and it is a policy Cedar accepts against the real schema
    bundle = engine.load(policy_dir(compiled.policy))
    assert len(bundle.annotations) == 2


@pytest.mark.parametrize("tool_input,expected", [
    (DESTRUCTIVE, "Deny"),
    (BENIGN, "Allow"),
])
def test_the_compiled_policy_gives_the_same_verdict_as_the_handwritten_one(
        tool_input, expected, policy_dir):
    """S3.3's acceptance test.

    The hand-written policies/core.cedar and the policy compiled from the rule
    it was modelled on must decide identically -- on the dangerous input *and*
    on the benign one, since a policy that denies everything would pass the
    first half alone.
    """
    compiled = compile_one(SMOKE_RULE, "agentspec:tests/test_enforcement.py")
    engine.load.cache_clear()
    from_rule = engine.decide(engine.load(policy_dir(compiled.policy)),
                              state(tool_input))
    engine.load.cache_clear()
    hand_written = engine.decide(engine.load(), state(tool_input))
    engine.load.cache_clear()

    assert from_rule.decision == hand_written.decision == expected
    assert from_rule.advice == hand_written.advice


# ------------------------------------------------------- the §C.6 mapping

def test_trigger_becomes_a_resource_constraint():
    assert 'resource == AgentGuard::Tool::"python_repl"' in \
        compile_one(rule()).policy


def test_trigger_any_drops_the_constraint():
    """`any` means every tool, so the scope must not name one."""
    policy = compile_one(rule(trigger="any")).policy

    assert "AgentGuard::Tool::" not in policy
    assert "resource\n)" in policy


def test_alternation_becomes_a_membership_test():
    """Cedar's scope takes a single entity uid, so `A | B` moves into `when`."""
    policy = compile_one(rule(trigger="python_repl | shell")).policy

    assert 'resource in [AgentGuard::Tool::"python_repl", ' \
           'AgentGuard::Tool::"shell"]' in policy


def test_a_dotted_trigger_keeps_its_dots():
    policy = compile_one(rule(trigger="Gmail.SendMail")).policy

    assert 'Tool::"Gmail.SendMail"' in policy


def test_a_leading_act_is_stripped():
    """docs/findings.md D-10: our grammar reads `act X` as a two-word name."""
    ir, errors = ag_compile.parse_rule(rule(trigger="act python_repl"))

    assert errors == []
    assert ir.events == ("python_repl",)


def test_checks_become_guarded_flag_tests():
    policy = compile_one(rule(check="destuctive_os_inst")).policy

    assert ("context.flags has destuctive_os_inst && "
            "context.flags.destuctive_os_inst") in policy


def test_a_negated_check_still_requires_the_sensor_to_have_run():
    """`!p` is "p was evaluated and came back false", not "p is absent".

    Compiling it to `!(flags has p)` would make the rule fire whenever nobody
    looked -- the opposite of what the author asked for.
    """
    policy = compile_one(rule(check="!destuctive_os_inst")).policy

    assert ("context.flags has destuctive_os_inst && "
            "!context.flags.destuctive_os_inst") in policy


def test_several_checks_are_conjoined():
    policy = compile_one(
        rule(check="involve_system_file\n    submit_post_request")).policy

    assert policy.count("context.flags has") == 2
    assert "&&" in policy


def test_check_true_adds_no_condition():
    compiled = compile_one(rule(check="true"))

    assert compiled.ok
    assert "context.flags" not in compiled.policy


@pytest.mark.parametrize("enforce", ["stop", "skip", "user_inspection",
                                     "llm_self_reflect"])
def test_each_enforcement_becomes_a_forbid_with_its_advice(enforce):
    policy = compile_one(rule(enforce=enforce)).policy

    assert policy.startswith("@id(")
    assert f'@advice("{enforce}")' in policy
    assert "forbid (" in policy


def test_llm_self_examine_is_normalised():
    """The README's name and the grammar's name are the same outcome (D-7)."""
    policy = compile_one(rule(enforce="llm_self_examine")).policy

    assert '@advice("llm_self_reflect")' in policy


def test_an_enforcement_message_is_kept():
    policy = compile_one(
        rule(enforce='user_inspection("make sure it is reasonable")')).policy

    assert '@message("make sure it is reasonable")' in policy


def test_invoke_action_becomes_a_substitution():
    compiled = compile_one(
        rule(enforce='invoke_action(safe_tool, {"path": "."})'))

    assert '@advice("substitute")' in compiled.policy
    assert '@substitute_tool("safe_tool")' in compiled.policy
    assert "@substitute_args('" in compiled.policy
    args = compiled.policy.split("@substitute_args('")[1].split("')")[0]
    assert json.loads(args) == {"path": "."}


def test_every_rule_carries_its_provenance():
    compiled = compile_one(rule(), "agentspec:src/rules/manual/pythonrepl.ar")

    assert '@source("agentspec:src/rules/manual/pythonrepl.ar#r")' in compiled.policy


# --------------------------------------------------- why rules do not compile

def test_enforce_none_is_dropped_with_a_reason():
    compiled = compile_one(rule(enforce="none"))

    assert not compiled.ok
    assert "nothing to forbid" in compiled.reason


def test_an_unregistered_predicate_is_reported_by_name():
    """docs/findings.md D-3: the corpus names predicates nothing registers."""
    compiled = compile_one(rule(check="is_malware"))

    assert not compiled.ok
    assert "is_malware" in compiled.reason
    assert "is_malware" not in sensors.SENSORS


def test_a_parameterised_predicate_cannot_become_a_flag():
    compiled = compile_one(rule(trigger="python_repl", check="v_f_disL(10)"))

    assert not compiled.ok
    assert "v_f_disL" in compiled.reason
    assert "nullary" in compiled.reason


def test_a_non_invoke_trigger_is_reported():
    compiled = compile_one(rule(trigger="state_change"))

    assert not compiled.ok
    assert "action invoke" in compiled.reason


def test_config_enforcement_has_no_cedar_equivalent():
    compiled = compile_one(
        rule(trigger="python_repl", check="true",
             enforce="real:obstacle:Min_stop_distance = 10"))

    assert not compiled.ok
    assert "config" in compiled.reason


def test_a_rule_can_be_blocked_for_several_reasons_at_once():
    """An apollo rule fails on trigger, predicate *and* enforcement.

    Reporting only the first would understate what bringing it across takes,
    which is exactly what S3.5's table is for.
    """
    compiled = compile_one(
        rule(trigger="state_change", check="v_f_disL(10)",
             enforce="real:obstacle:Min_stop_distance = 10"))

    assert not compiled.ok
    assert len(compiled.reasons) == 3


def test_a_rule_that_does_not_parse_says_so():
    compiled = compile_one(
        "rule @broken\ntrigger\n    python_repl\ncheck\n    p(e.g. prose)\n"
        "enforce\n    stop\nend\n")

    assert not compiled.ok
    assert "does not parse" in compiled.reason


# --------------------------------------------------------------- the corpus

def corpus_files():
    files = sorted(glob.glob(os.path.join(REPO_ROOT, "src/rules/**/*.ar"),
                             recursive=True))
    files += sorted(glob.glob(os.path.join(REPO_ROOT, "src/rules/**/*.rule"),
                              recursive=True))
    return files


def compile_corpus():
    return [c for path in corpus_files() for c in ag_compile.compile_file(path)]


def test_the_corpus_compiles_at_the_rate_we_think_it_does():
    """Pinned so S3.4/S3.5 report a number that cannot drift silently."""
    results = compile_corpus()

    assert len(results) == 62
    assert sum(1 for c in results if c.ok) == 18


def test_the_compiled_corpus_has_to_be_partitioned_by_domain():
    """Found by the engine's own startup check, and it is a real constraint.

    An engine runs one domain's sensors (S2.3) and refuses to start on a policy
    keyed on a flag it will never materialise (S2.5). So the whole corpus in one
    policy file does not load -- and should not. S3.4 has to write one file per
    domain.
    """
    by_domain = {}
    for compiled in compile_corpus():
        if compiled.ok:
            by_domain.setdefault(compiled.domain, []).append(compiled.rule_id)

    assert set(by_domain) == {"code", "embodied", None}
    assert len(by_domain["code"]) == 10
    assert len(by_domain["embodied"]) == 1
    # `None` reads no flags at all (`check true`), so it fits either file.
    assert len(by_domain[None]) == 7


@pytest.mark.parametrize("domain,count", [("code", 10), ("embodied", 1)])
def test_each_domains_policies_load_into_an_engine_for_that_domain(
        domain, count, policy_dir):
    """A policy that does not validate is not a compilation, it is a bug."""
    policies = "\n".join(c.policy for c in compile_corpus()
                         if c.ok and c.domain in (domain, None))
    bundle = engine.load(policy_dir(policies), domain)

    assert len(bundle.annotations) == count + 7 + 1   # + agnostic + baseline
    assert bundle.domain == domain


def test_every_failure_gives_at_least_one_reason():
    for compiled in compile_corpus():
        if not compiled.ok:
            assert compiled.reasons, compiled.rule_id
            assert all(r.strip() for r in compiled.reasons)


# ------------------------------------------------ the generated tree (S3.4)

GENERATED = os.path.join(REPO_ROOT, "policies", "generated")


def test_the_generated_tree_exists_and_is_current():
    """S3.4: `policies/generated/` populated. Regenerate with `make compile-corpus`."""
    import subprocess                                   # noqa: PLC0415

    for name in ("code", "embodied", "llm"):
        directory = os.path.join(GENERATED, name)
        assert os.path.isfile(os.path.join(directory, "rules.cedar")), name
        assert os.path.isfile(os.path.join(directory, "schema.cedarschema")), name
    assert os.path.isfile(os.path.join(GENERATED, "coverage.json"))

    # and it matches what the compiler produces right now
    before = {}
    for root, _dirs, names in os.walk(GENERATED):
        for name in names:
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as handle:
                before[path] = handle.read()

    subprocess.run([sys.executable, os.path.join(REPO_ROOT, "tools",
                                                 "compile_corpus.py"), "--quiet"],
                   check=True, cwd=REPO_ROOT, capture_output=True)

    for path, text in before.items():
        with open(path, encoding="utf-8") as handle:
            assert handle.read() == text, (
                f"{path} is stale -- run `make compile-corpus`")


def test_every_generated_policy_validates():
    """S3.4's acceptance. Each directory is checked against its own schema."""
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    import validate_policies as vp                      # noqa: PLC0415

    for name in ("code", "embodied", "llm"):
        directory = os.path.join(GENERATED, name)
        schema = vp.load_schema(os.path.join(directory, "schema.cedarschema"))
        ok, messages = vp.check(os.path.join(directory, "rules.cedar"), schema)
        assert ok, (name, messages)


@pytest.mark.parametrize("name,domain", [("code", "code"),
                                         ("embodied", "embodied")])
def test_the_shipped_domains_load_into_an_engine(name, domain):
    """A generated directory is meant to be usable, not just well-formed."""
    engine.load.cache_clear()
    bundle = engine.load(os.path.join(GENERATED, name), domain)
    engine.load.cache_clear()

    assert bundle.domain == domain
    assert bundle.annotations


def test_the_llm_directory_validates_but_will_not_load():
    """Declaring a flag is not the same as being able to observe it.

    The LLM rules bring the source of their own predicates, so the schema beside
    them declares flags the registry does not have. Cedar is satisfied. The
    engine is not, because no *sensor* produces them -- and that gap is exactly
    what the S2.5 coverage check exists to catch.
    """
    engine.load.cache_clear()
    with pytest.raises(engine.PolicyError) as exc:
        engine.load(os.path.join(GENERATED, "llm"), "embodied")
    engine.load.cache_clear()

    assert "never materialised" in str(exc.value)

    with open(os.path.join(GENERATED, "llm", "rules.cedar"),
              encoding="utf-8") as handle:
        assert "WILL NOT LOAD" in handle.read(), "the file must say so too"


def test_the_llm_rules_compile_only_because_they_carry_their_predicates():
    """The RQ1 contrast, in one assertion.

    The human-written corpus compiles at 18/62, mostly because it names
    predicates nothing registers (D-3). The generated rules compile at 20/20 --
    and at 0/20 if you refuse to count the predicates they define. Same
    compiler; the difference is entirely whether the rule brought its detector.
    """
    import glob as _glob                                # noqa: PLC0415

    paths = sorted(_glob.glob(os.path.join(REPO_ROOT,
                                           "src/rules/llm/generated_rules-*.jsonl")))
    assert paths

    with_own = [c for p in paths for c in ag_compile.compile_llm_file(p)]
    registry_only = [c for p in paths
                     for c in ag_compile.compile_llm_file(
                         p, known_flags=set(sensors.FLAGS))]

    assert sum(1 for c in with_own if c.ok) == 20
    assert sum(1 for c in registry_only if c.ok) == 0


def test_predicate_names_are_parsed_never_executed():
    """Model-written Python arrives in a data file. We read it, we do not run it."""
    marker = []
    source = ("def sneaky(user_input, tool_input, steps):\n"
              "    __import__('sys').modules['pytest'].MARKED = True\n"
              "    return True\n")

    assert ag_compile.predicate_names(source) == ("sneaky",)
    assert not hasattr(pytest, "MARKED"), "the predicate source was executed"
    assert marker == []


def test_coverage_json_records_every_rule_and_its_reasons():
    """S3.5 reads this file, so it has to carry the whole picture."""
    with open(os.path.join(GENERATED, "coverage.json"), encoding="utf-8") as handle:
        coverage = json.load(handle)

    assert coverage["shipped"]["total"] == 62
    assert coverage["shipped"]["compiled"] == 18
    assert coverage["llm"]["total"] == 20
    assert coverage["llm"]["compiled"] == 20
    assert len(coverage["llm_flags_defined"]) == 22

    for entry in coverage["shipped"]["rules"]:
        assert entry["ok"] or entry["reasons"], entry["id"]
