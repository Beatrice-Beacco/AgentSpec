"""Per-step latency instrumentation, off unless AGENTSPEC_PROFILE=1.

Splits an agent step into the four phases we need for RQ5 (plan.md S0.11, S2.9):

    llm_plan        the model deciding what to do
    rule_parse      re-lexing and re-parsing every triggered rule's text
    predicate_eval  walking the tree, which is where predicates actually run
    enforcement     applying the chosen enforcement strategy

The split matters because the thesis claim is that a policy engine is cheap and
*detection* is what costs -- a claim you can only make if the two are measured
apart. It also exposes rule_parse, which AgentSpec pays on every single action
because RuleInterpreter.verify_and_enforce re-parses the raw rule text each time.

Disabled, every entry point is a single module-level bool check.
"""
import json
import os
import threading
import time
from contextlib import contextmanager

ENABLED = os.environ.get("AGENTSPEC_PROFILE") == "1"
PATH = os.environ.get("AGENTSPEC_PROFILE_PATH",
                      os.path.join("expres", "latency", "baseline.jsonl"))

PHASES = ("llm_plan", "rule_parse", "predicate_eval", "enforcement")

# One record per in-flight step. Thread-local because LangChain may run
# callbacks off-thread; a shared dict would interleave two agents' timings.
_local = threading.local()


def _current():
    return getattr(_local, "record", None)


def begin_step(**meta):
    if not ENABLED:
        return
    _local.record = {
        "t0": time.perf_counter(),
        "meta": meta,
        "phases": dict.fromkeys(PHASES, 0.0),
        "rules_evaluated": 0,
    }


@contextmanager
def phase(name):
    """Accumulate time into `name` for the current step.

    Accumulates rather than assigns: a step that triggers three rules pays
    rule_parse three times, and the total is what we care about.
    """
    record = _current()
    if not ENABLED or record is None:
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        record["phases"][name] += time.perf_counter() - start


def count_rule():
    record = _current()
    if ENABLED and record is not None:
        record["rules_evaluated"] += 1


def end_step(**extra):
    """Write one JSON line and clear the current step. Safe to call twice."""
    record = _current()
    if not ENABLED or record is None:
        return
    _local.record = None

    ms = lambda s: round(s * 1000, 4)                    # noqa: E731
    phases = record["phases"]
    line = {
        "ts": round(time.time(), 3),
        **record["meta"],
        **extra,
        "rules_evaluated": record["rules_evaluated"],
        **{f"{name}_ms": ms(phases[name]) for name in PHASES},
        "guard_ms": ms(sum(phases[n] for n in PHASES if n != "llm_plan")),
        "total_ms": ms(time.perf_counter() - record["t0"]),
    }

    directory = os.path.dirname(PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(PATH, "a") as handle:
        handle.write(json.dumps(line) + "\n")
