// AgentGuard core policies -- the walking skeleton's policy set (plan.md S1.6).
//
// Two policies, deliberately: the smallest set that can reach both verdicts and
// carry an enforcement outcome out with them. The corpus port is S3.4's job.
//
// Validate with `make validate` (tools/validate_policies.py).

// --------------------------------------------------------------------------
// 1. Baseline capability grant.
//
// Unconditional, which is *not* the fail-closed baseline of thesis §C.3 pattern
// ①. That is intentional and temporary: S1.7's acceptance test is verdict parity
// with the legacy engine, and AgentSpec is allow-unless-a-rule-fires. Making the
// baseline fail-closed here would change the verdicts, so the comparison would
// no longer be measuring the thing it claims to measure.
//
// The fail-closed baseline (`when { resource.kind == "read_only" }`, plus
// explicit grants per tool kind) arrives with S2.7, once the entity store
// actually carries Tool.kind for every tool and the parity suite runs on both
// engines. Track it there, not here.
// --------------------------------------------------------------------------

@id("baseline_allow_tools")
permit (
  principal,
  action == AgentGuard::Action::"invoke",
  resource
);

// --------------------------------------------------------------------------
// 2. Stop a destructive filesystem call from the Python REPL.
//
// `destuctive_os_inst` (sic -- the misspelling is AgentSpec's, in both the
// grammar token and the predicate function) matches os.remove / os.unlink, or
// pathlib and unlink together. It is a Python regex over the tool input, so it
// cannot run inside a policy: Cedar expressions are pure and total. The sensor
// runs first and its result arrives as a member of context.flags. That split is
// the architecture (thesis M1); this policy is the smallest thing that depends
// on it.
//
// @advice carries the enforcement outcome, because Cedar only answers
// Allow/Deny and AgentSpec has five outcomes. It is read back off the
// determining policies via policies_to_json_str() -- see docs/spikes.md S1.2 for
// why id_annotations_by_reason is not enough.
//
// @source points at the test suite, not the shipped corpus, and the difference
// is worth knowing. The nearest corpus rule is pythonrepl.ar#index8
// (`@desctuct_system_file`), and it is weaker in two ways: it also requires
// `involve_system_file`, so a delete outside a system path does not match it,
// and it enforces `user_inspection` rather than `stop`. That is not an outlier
// -- 24 of the 26 rules in pythonrepl.ar enforce `user_inspection`. Of the two
// that stop, one is `is_malware`, whose predicate is never registered in
// predicate_table (S0.12), so it can never fire. The shipped PythonREPL corpus
// has exactly one working hard stop.
// --------------------------------------------------------------------------

@id("no_destructive_os_call")
@advice("stop")
@source("agentspec:tests/test_enforcement.py#BLOCK_DELETION")
forbid (
  principal,
  action   == AgentGuard::Action::"invoke",
  resource == AgentGuard::Tool::"python_repl"
)
when { context.flags.contains("destuctive_os_inst") };
