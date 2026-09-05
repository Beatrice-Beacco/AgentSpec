# Short, path-free entry points for the test suite.
# Always run from the repo root: `cd` here first, then `make test`.

VENV := .venv
PY   := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest

.PHONY: help test test-verbose test-why test-enforcement test-parsing audit venv clean

help:  ## show this help
	@grep -hE '^[a-z-]+:.*?##' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

$(PYTEST):
	@echo "pytest not installed in $(VENV) — installing"
	@$(VENV)/bin/pip install -q pytest

test: $(PYTEST)  ## run the whole suite (expect: 17 passed, 8 xfailed)
	@$(PYTEST) -q

test-verbose: $(PYTEST)  ## run with the agent trace + outcome blocks
	@AGENTSPEC_VERBOSE=1 $(PYTEST) -s -q tests/test_enforcement.py

test-why: $(PYTEST)  ## show why each of the 8 grammar xfails fails
	@$(PYTEST) -rxX -q tests/test_rule_parsing.py

test-enforcement: $(PYTEST)  ## just the enforcement tests, named
	@$(PYTEST) -v tests/test_enforcement.py

test-parsing: $(PYTEST)  ## just the grammar probes, with real ANTLR errors
	@$(PYTEST) --runxfail -q tests/test_rule_parsing.py

audit:  ## parse-check every shipped .ar / .rule file
	@$(PY) tools/audit_rules.py src

venv:  ## create .venv and install pinned deps
	@python3 -m venv $(VENV)
	@$(VENV)/bin/pip install -q --upgrade pip
	@$(VENV)/bin/pip install -q \
		"langchain==0.3.25" "langchain-core==0.3.86" "langchain-community==0.3.25" \
		"langchain-experimental==0.3.4" "antlr4-python3-runtime==4.13" pytest
	@echo "venv ready — run: make test"

clean:  ## remove caches
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache
