# Course checks. `make test` runs every reference test suite offline.
PY ?= python
SUITES = \
	phases/01-fastapi-pydantic-problem-details/solution/cost-api \
	phases/02-focus-on-bigquery/solution/cost-api \
	phases/02-focus-on-bigquery \
	phases/03-mcp-tools-with-fastmcp/solution/mcp-finops \
	phases/04-llm-gateway-and-vertex-ai/solution/llm-toolkit \
	phases/05-multi-agent-adk-and-langgraph/solution/agents \
	phases/06-security-and-governance/solution/security \
	phases/06-security-and-governance/solution/cost-api \
	phases/06-security-and-governance/solution/mcp-finops \
	phases/08-gcp-sizing-and-constraints \
	phases/09-devops-and-delivery

.PHONY: install test lint data-check java-domain

install:   ## everything the reference suites need, in the current environment
	$(PY) -m pip install -r requirements-dev.txt

test:
	@set -e; for s in $(SUITES); do echo "== $$s"; (cd $$s && $(PY) -m pytest -q -p no:cacheprovider); done

lint:
	ruff check phases data

data-check:  ## the committed sample data must match the generator
	$(PY) data/generate_sample.py --out /tmp/focus_check.csv && cmp /tmp/focus_check.csv data/sample/focus_costs.csv

java-domain:  ## compile the pure-Java domain without Maven
	mkdir -p /tmp/ledger-domain && javac -d /tmp/ledger-domain phases/07-java-integration/solution/ledger-java/src/main/java/com/costpilot/ledger/domain/*.java
