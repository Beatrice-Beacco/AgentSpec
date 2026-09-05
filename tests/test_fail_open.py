"""A safety mechanism must fail closed. AgentSpec fails four different ways.
(plan.md S0.12)

`Rule.from_text` calls `parser.program()` without `removeErrorListeners()`, so
ANTLR's default listener prints to stderr and *recovers*. Nothing checks the
result. What happens next depends on where in the rule the error lands and,
absurdly, on how many tokens a comment contains:

  1. silent acceptance  -- the rule loads, then raises ValueError mid-run when
                           RuleInterpreter re-parses it WITH a raising listener
  2. silent truncation  -- `trigger Gmail.SendMail` loads as event "Gmail",
                           so the rule arms on a different tool than written
  3. internal crash     -- a two-token comment breaks recovery hard enough that
                           the listener never sets `event`, and load fails with
                           AttributeError naming a private class
  4. unregistered names -- a rule may name a predicate that exists in the source
                           but was never added to predicate_table

Each xfail(strict=True) states what *should* happen; the plain tests beside it
record what does. The xfails turn green at plan.md S2.5, when the Cedar engine
validates the policy set at startup and refuses to run on failure. That is RQ6.
"""
import re

import pytest

from agent import Action
from interpreter import RuleInterpreter
from rule import Rule
from rules.manual.table import predicate_table
from state import RuleState


def rule_text(trigger="python_repl", check="true", enforce="stop", prefix=""):
    return (f"{prefix}rule @looks_fine\ntrigger\n    {trigger}\n"
            f"check\n    {check}\nenforce\n    {enforce}\nend\n")


# `check True` is capitalised, as in src/rules/manual/toolemu.ar. The trigger
# clause parses, so the listener sets `event` and the rule loads.
BAD_CHECK = rule_text(check="True")

# `is_malware` is the first rule in src/rules/manual/pythonrepl.ar. Defined in
# rules/manual/pythonrepl.py, never registered in predicate_table.
UNREGISTERED = rule_text(check="is_malware")

# One token after `//` recovers; two do not. Both are ordinary comments.
COMMENT_ONE_TOKEN = rule_text(check="True", prefix="//index1\n")
COMMENT_TWO_TOKENS = rule_text(check="True", prefix="// index 0\n")


def enforce(rule_or_text):
    """Drive one rule through the interpreter the way the executor does."""
    rule = (rule_or_text if isinstance(rule_or_text, Rule)
            else Rule.from_text(rule_or_text))
    action = Action(name="python_repl", input="print(1)", action=None)
    state = RuleState(action=action, agent=None, intermediate_steps=[],
                      user_input="anything")
    return RuleInterpreter(rule, state).verify_and_enforce(action)


# ------------------------------------------------------ what should happen

@pytest.mark.xfail(strict=True, reason=(
    "Rule.from_text does not call removeErrorListeners(), so ANTLR recovers "
    "and the malformed rule is accepted as if valid."))
def test_malformed_rule_is_rejected():
    with pytest.raises(Exception):
        Rule.from_text(BAD_CHECK)


@pytest.mark.xfail(strict=True, reason=(
    "A rule that failed to parse should not be able to take the agent down. "
    "verify_and_enforce re-parses with a raising listener, so the error lands "
    "mid-run instead of at load."))
def test_malformed_rule_does_not_crash_at_enforcement():
    enforce(BAD_CHECK)


@pytest.mark.xfail(strict=True, reason=(
    "`trigger Gmail.SendMail` should be rejected, not silently truncated to a "
    "different tool name."))
def test_dotted_trigger_is_rejected_rather_than_truncated():
    assert Rule.from_text(rule_text(trigger="Gmail.SendMail")).event != "Gmail"


@pytest.mark.xfail(strict=True, reason=(
    "`is_malware` is defined in rules/manual/pythonrepl.py but absent from "
    "predicate_table, making the rule unsatisfiable. Nothing checks at load."))
def test_rule_naming_an_unregistered_predicate_is_rejected():
    with pytest.raises(Exception):
        Rule.from_text(UNREGISTERED)


# ------------------------------------------------------ what actually happens

def test_malformed_rule_is_accepted_today():
    rule = Rule.from_text(BAD_CHECK)
    assert (rule.id, rule.event) == ("looks_fine", "python_repl")


def test_malformed_rule_raises_valueerror_at_enforcement_today():
    """The error arrives during an agent run, at the worst possible moment."""
    with pytest.raises(ValueError, match=r"Syntax error at line \d+"):
        enforce(BAD_CHECK)


def test_unregistered_predicate_also_fails_only_at_enforcement_today():
    with pytest.raises(ValueError, match=r"Syntax error at line \d+"):
        enforce(UNREGISTERED)


def test_dotted_trigger_is_silently_truncated_today():
    """The most dangerous of the four: the rule loads and arms on the wrong tool.

    Written as `Gmail.SendMail`, it becomes event `Gmail` — so it never fires on
    the intended action, and would fire on a tool actually named `Gmail`.
    """
    assert Rule.from_text(rule_text(trigger="Gmail.SendMail")).event == "Gmail"


@pytest.mark.parametrize("comment,outcome", [
    ("//index1\n", "accepted"),          # one token after //
    ("// index 0\n", "AttributeError"),  # two tokens after //
])
def test_comment_failure_mode_depends_on_word_count(comment, outcome):
    """Identical-looking comments load or crash depending on their word count.

    Neither is valid — the grammar has no comment token at all. With one token
    ANTLR recovers and `event` gets set; with two the trigger clause is never
    entered, and Rule.from_text dies on an unset attribute of a private class.
    """
    text = rule_text(check="True", prefix=comment)
    if outcome == "accepted":
        assert Rule.from_text(text).event == "python_repl"
    else:
        with pytest.raises(AttributeError, match="RuleParser.*has no attribute"):
            Rule.from_text(text)


# ------------------------------------------------- how far the gap reaches

def used_predicates(path):
    names = set()
    for chunk in open(path).read().split("rule @")[1:]:
        match = re.search(r"check\s*\n((?:\s+\S.*\n?)*)", chunk)
        if match:
            names |= {line.strip().lstrip("!")
                      for line in match.group(1).splitlines() if line.strip()}
    return names - {"true", "false", "True", "False"}


def test_shipped_rules_reference_unregistered_predicates():
    """The shipped corpus contains rules that could never have fired.

    Pinned to the current count so a change is deliberate. If this fails after
    a fix, that is progress — update the number.
    """
    missing = sorted(name for name in used_predicates("src/rules/manual/pythonrepl.ar")
                     if name not in predicate_table)
    assert len(missing) == 17, missing
    assert "is_malware" in missing


def test_grammar_and_registry_agree():
    """Checked, and they do — the 36 names match exactly, so this is not a gap.

    Recorded as a test so the claim is backed by more than a one-off script, and
    so a future grammar edit that desyncs the two fails loudly.
    """
    grammar = re.search(r"PREDICATE:(.*?);",
                        open("src/spec_lang/AgentSpec.g4").read(), re.S).group(1)
    assert {p.strip().strip("'") for p in grammar.split("|")} == set(predicate_table)
