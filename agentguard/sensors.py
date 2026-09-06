"""The sensor registry (plan.md S2.1).

A sensor is one of AgentSpec's predicates plus the metadata the engine needs to
use it responsibly. The predicates themselves are untouched third-party code in
`src/rules/manual/`; this module wraps them and answers four questions about
each one that the bare `predicate_table` cannot:

    name     what flag it contributes to `context.flags`
    domain   which agent it belongs to -- code, embodied, shell, toolemu
    reads    which of (user_input, tool_input, intermediate_steps) it touches
    cost     what running it costs, on the scale that ordering decisions need

`domain` is not decoration. Running an embodied sensor over a code agent's
trace is a **TypeError, not a False**: the embodied predicates expect
`intermediate_steps` shaped as their own observations, and LangChain hands them
(action, observation) tuples. Six of the 36 raise on ordinary code-agent input.
So the domain field is what stops the engine evaluating a sensor that cannot
apply, and S2.3 selects on it.

Everything is derived from the predicates themselves rather than hand-listed,
so adding one to `predicate_table` produces a correct Sensor with no edit here.
That matters for S2.2, which generates the Cedar schema from `FLAGS`: a
hand-maintained table would put a manual step back in the middle of codegen.
"""
import ast
import functools
import inspect
import textwrap
import warnings
from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple

import agentguard  # noqa: F401  -- puts src/ on sys.path

from rules.manual.table import predicate_table

# ------------------------------------------------------------------ domains

CODE = "code"          # RedCode / PythonREPL: regexes over generated source
EMBODIED = "embodied"  # SafeAgentBench: household actions in a simulator
SHELL = "shell"        # ShellTool
TOOLEMU = "toolemu"    # ToolEmu's emulated SaaS toolkits
UNKNOWN = "unknown"

DOMAINS = (CODE, EMBODIED, SHELL, TOOLEMU)

MODULE_DOMAIN = {
    "rules.manual.pythonrepl": CODE,
    "rules.manual.embodied": EMBODIED,
    "rules.manual.terminal": SHELL,
    "rules.manual.toolemu": TOOLEMU,
}

# -------------------------------------------------------------------- costs

INPUT = "input"      # a pure function of the proposed action; microseconds
HISTORY = "history"  # also walks intermediate_steps; grows with the run
MODEL = "model"      # calls an LLM; network latency, money, non-determinism

#: Cheapest first. The engine may reorder sensors within a decision but never
#: across this ordering, so an expensive sensor is never paid for a flag a
#: cheap one has already settled.
COSTS = (INPUT, HISTORY, MODEL)

#: Functions whose use makes a sensor cost MODEL.
MODEL_CALLS = frozenset({"llm_judge"})

#: The predicate signature, in order. `reads` is a subset of these.
PARAMETERS = ("user_input", "tool_input", "intermediate_steps")


@dataclass(frozen=True)
class Sensor:
    """One predicate, plus what the engine needs to know before running it."""
    name: str
    domain: str
    reads: Tuple[str, ...]
    cost: str
    flags: Tuple[str, ...]
    predicate: Callable[..., Any]

    def __call__(self, user_input, tool_input, intermediate_steps) -> bool:
        """Evaluate the predicate. Exceptions propagate -- see `evaluate`."""
        return bool(self.predicate(user_input, tool_input, intermediate_steps))


# ------------------------------------------------------------------ deriving

def _references(predicate):
    """Every bare name appearing in the predicate's body, and every name it calls.

    Static and exact for direct references, which is all the metadata needs.
    Falls back to "assume the worst" when the source is unavailable (a C
    extension, a lambda, a zipimport): claiming a predicate reads nothing and
    costs nothing would under-report, and under-reporting cost is the direction
    that hurts.
    """
    try:
        source = textwrap.dedent(inspect.getsource(predicate))
        with warnings.catch_warnings():
            # rules/manual/pythonrepl.py has unescaped regexes in plain strings
            # ("\.recv"). Compiling it already warned once at import; parsing
            # it again here would repeat that in every test run, attributing a
            # corpus wart to this module.
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except (OSError, TypeError, SyntaxError):
        return set(PARAMETERS), set(MODEL_CALLS)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    calls = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    return names, calls


def _sensor(name, predicate):
    names, calls = _references(predicate)
    reads = tuple(p for p in PARAMETERS if p in names)
    if calls & MODEL_CALLS:
        cost = MODEL
    elif "intermediate_steps" in reads:
        cost = HISTORY
    else:
        cost = INPUT
    return Sensor(
        name=name,
        domain=MODULE_DOMAIN.get(getattr(predicate, "__module__", ""), UNKNOWN),
        reads=reads,
        cost=cost,
        # One flag per sensor, named after it, because that is what an
        # AgentSpec `check` clause names and what a compiled policy will test.
        # A tuple rather than a string because S4.1's taint sensors set several
        # (`read_secret`, `fetched_untrusted`) and S2.2 consumes the union.
        flags=(name,),
        predicate=predicate,
    )


@functools.lru_cache(maxsize=1)
def _build() -> Dict[str, Sensor]:
    return {name: _sensor(name, predicate)
            for name, predicate in sorted(predicate_table.items())}


SENSORS: Dict[str, Sensor] = _build()

#: Every flag any sensor can set. This is S2.2's input: the Cedar schema's
#: `context.flags` record is generated from exactly this tuple.
FLAGS: Tuple[str, ...] = tuple(sorted(
    flag for sensor in SENSORS.values() for flag in sensor.flags
))


# ------------------------------------------------------------------ querying

def by_domain(domain) -> Tuple[Sensor, ...]:
    """Sensors for one domain, cheapest first."""
    return tuple(sorted((s for s in SENSORS.values() if s.domain == domain),
                        key=lambda s: (COSTS.index(s.cost), s.name)))


def by_cost(cost) -> Tuple[Sensor, ...]:
    return tuple(s for s in SENSORS.values() if s.cost == cost)


def get(name) -> Sensor:
    """Look a sensor up, failing loudly on a typo.

    AgentSpec's own failure here is silent: `RuleInterpreter.eval_predicate`
    does `predicate_table[name]`, so a rule naming an unregistered predicate
    raises KeyError *mid-run* -- `is_malware`, the corpus's very first rule,
    does exactly that (S0.12). Resolving names at construction moves it.
    """
    try:
        return SENSORS[name]
    except KeyError:
        raise KeyError(
            f"no sensor named {name!r}; "
            f"{len(SENSORS)} are registered in rules.manual.table.predicate_table"
        ) from None


def evaluate(sensor, user_input, tool_input, intermediate_steps) -> bool:
    """Run one sensor. Exceptions are **not** caught.

    A sensor that raises would otherwise leave its flag unset, which reads to
    Cedar as "the dangerous thing is not happening" -- a safety policy that
    silently never fires, the failure mode tests/test_fail_open.py documents.
    Crashing loudly is worse for uptime and better for safety. S2.3 replaces
    this with an explicit fail-closed flag rather than a traceback.
    """
    return sensor(user_input, tool_input, intermediate_steps)


def _report():
    """`python -m agentguard.sensors` -- the registry as a table.

    Exists so the registry can be *looked at* rather than only imported: S2.2
    generates the schema from it, and a codegen input you cannot read is a
    codegen input you cannot review.
    """
    print(f"{'sensor':38s} {'domain':9s} {'cost':8s} reads")
    print("-" * 96)
    for domain in DOMAINS:
        for sensor in by_domain(domain):
            print(f"{sensor.name:38s} {sensor.domain:9s} {sensor.cost:8s} "
                  f"{', '.join(sensor.reads) or '-'}")
    counts = {d: len(by_domain(d)) for d in DOMAINS}
    costs = {c: len(by_cost(c)) for c in COSTS}
    print(f"\n{len(SENSORS)} sensors, {len(FLAGS)} flags")
    print(f"  by domain: {counts}")
    print(f"  by cost  : {costs}")


if __name__ == "__main__":
    _report()
