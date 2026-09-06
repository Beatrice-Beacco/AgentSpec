# Short, path-free entry points for the test suite.
# Always run from the repo root: `cd` here first, then `make test`.

VENV := .venv
PY   := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest

.PHONY: help test test-verbose test-why test-enforcement test-parsing test-schema test-cedar audit audit-freeze profile profile-freeze spikes spike-hello spike-annotations spike-validation spike-latency validate sensors schema golden ui venv clean

help:  ## show this help
	@grep -hE '^[a-z-]+:.*?##' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

$(PYTEST):
	@echo "pytest not installed in $(VENV) - installing from requirements-dev.txt"
	@$(VENV)/bin/pip install -q -r requirements-dev.txt

test: $(PYTEST)  ## run the whole suite (expect: 439 passed, 13 xfailed)
	@$(PYTEST) -q

test-verbose: $(PYTEST)  ## run with the agent trace + outcome blocks
	@AGENTSPEC_VERBOSE=1 $(PYTEST) -s -q tests/test_enforcement.py

test-why: $(PYTEST)  ## show why each of the 8 grammar xfails fails
	@$(PYTEST) -rxX -q tests/test_rule_parsing.py

test-enforcement: $(PYTEST)  ## just the enforcement tests, named
	@$(PYTEST) -v tests/test_enforcement.py

test-parsing: $(PYTEST)  ## just the grammar probes, with real ANTLR errors
	@$(PYTEST) --runxfail -q tests/test_rule_parsing.py

test-schema: $(PYTEST)  ## just the Cedar schema tests, named
	@$(PYTEST) -v tests/test_schema.py

sensors:  ## list the sensor registry (name, domain, cost, reads)
	@$(PY) -m agentguard.sensors

schema:  ## regenerate policies/schema.cedarschema from the sensor registry
	@$(PY) -m agentguard.schema

golden:  ## regenerate the S2.3 golden request (review the diff!)
	@$(PY) tests/golden_request.py

test-cedar: $(PYTEST)  ## run the whole suite on the Cedar engine (parity, S2.7)
	@AGENTGUARD=cedar $(PYTEST) -q -rs

validate:  ## check the schema is current and every policy validates
	@$(PY) tools/validate_policies.py

spikes: spike-hello spike-annotations spike-validation spike-latency  ## run every Cedar spike

spike-hello:  ## S1.1 - smallest Cedar decision (Allow + Deny)
	@$(PY) spikes/hello_cedar.py

spike-annotations:  ## S1.2 - reading @advice off determining policies
	@$(PY) spikes/annotations.py

spike-validation:  ## S1.3 - what validate_policies() catches at load
	@$(PY) spikes/validation.py

spike-latency:  ## S1.4 - 10k authorizations, mean/p99
	@$(PY) spikes/latency.py

ui:  ## start the test bench at http://127.0.0.1:5000
	@$(VENV)/bin/python -c "import flask" 2>/dev/null || $(VENV)/bin/pip install -q -r requirements-dev.txt
	@$(PY) ui/app.py

audit:  ## parse-check every shipped .ar / .rule file
	@$(PY) tools/audit_rules.py src

profile:  ## time the suite and report per-phase latency
	@rm -f expres/latency/baseline.jsonl
	@AGENTSPEC_PROFILE=1 $(PYTEST) -q >/dev/null
	@$(PY) tools/latency_report.py expres/latency/baseline.jsonl

profile-freeze:  ## regenerate docs/baseline-latency.md (thesis evidence)
	@rm -f expres/latency/baseline.jsonl
	@AGENTSPEC_PROFILE=1 $(PYTEST) -q >/dev/null
	@$(PY) tools/latency_report.py expres/latency/baseline.jsonl > docs/baseline-latency.md
	@echo "wrote docs/baseline-latency.md"

audit-freeze:  ## regenerate docs/baseline-audit.md (thesis evidence)
	@$(PY) tools/audit_rules.py src > docs/baseline-audit.md 2>/dev/null
	@echo "wrote docs/baseline-audit.md"

venv:  ## create .venv from requirements-dev.txt
	@python3 -m venv $(VENV)
	@$(VENV)/bin/pip install -q --upgrade pip
	@$(VENV)/bin/pip install -q -r requirements-dev.txt
	@echo "venv ready - run: make test"

clean:  ## remove caches
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache
