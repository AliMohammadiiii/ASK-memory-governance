PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest
RUFF ?= $(PYTHON) -m ruff
MYPY ?= $(PYTHON) -m mypy

.DEFAULT_GOAL := help

.PHONY: help setup check release-check test test-fast lint format format-check \
	typecheck build shell-syntax compile smoke validate-data reproduce-mgp6 \
	reproduce-longmemeval figures paper paper-audit thesis clean repo-check

help:
	@echo "setup          Install the package and development tools"
	@echo "check          Run the fast, offline development gate"
	@echo "release-check  Run the complete offline release gate"
	@echo "test           Run the complete test suite"
	@echo "lint           Run Ruff lint checks"
	@echo "format         Format maintained Python code"
	@echo "typecheck      Run the supported mypy scope"
	@echo "build          Build sdist and wheel"

setup:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e '.[dev]'

check: repo-check lint format-check typecheck compile test-fast shell-syntax

release-check: check test validate-data build paper-audit

test:
	$(PYTEST) -q

test-fast:
	$(PYTEST) -q -m 'not slow and not network'

lint:
	$(RUFF) check src tests scripts benchmarks

format:
	$(RUFF) format src tests scripts benchmarks
	$(RUFF) check --fix src tests scripts benchmarks

format-check:
	$(RUFF) format --check src tests scripts benchmarks

typecheck:
	$(MYPY) --follow-imports=skip src/ask/controller src/ask/memory \
		src/ask/eval/mgp6.py src/ask/eval/mgp6_schema.py src/ask/eval/mgp6_v43.py

build:
	$(PYTHON) -m build
	$(PYTHON) scripts/release/verify_wheel.py --dist-dir dist

shell-syntax:
	git ls-files -z '*.sh' | xargs -0 bash -n

compile:
	$(PYTHON) -m compileall -q src scripts benchmarks tests

smoke:
	$(PYTHON) scripts/run_mgp6.py --systems no_memory --limit 1 --dry-run

validate-data:
	$(PYTHON) benchmarks/mgp6/validate_mgp6.py --input benchmarks/mgp6/data/mgp6_v2.jsonl --strict

reproduce-mgp6: validate-data
	$(PYTHON) benchmarks/mgp6/run_5systems.py --help

reproduce-longmemeval:
	$(PYTHON) scripts/run_baseline.py --help

figures:
	@echo 'Figure sources are under docs/figures; regenerate from machine-readable reports before submission.'

paper:
	@echo 'Paper sources are under paper/. Compile after selecting the official venue template.'

paper-audit:
	$(PYTHON) scripts/analysis/audit_mgp6_validity.py
	$(PYTHON) scripts/release/audit_bibliography.py

thesis:
	@echo 'Thesis source is under thesis/. Institutional metadata remains explicit placeholders.'

repo-check:
	$(PYTHON) scripts/validate_repository.py

clean:
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache htmlcov
	rm -f .coverage
	find src tests scripts benchmarks -type d -name __pycache__ -prune -exec rm -rf {} +
