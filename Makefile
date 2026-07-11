PYTHON ?= python
PYTEST ?= pytest

.PHONY: setup test test-fast lint format typecheck build smoke validate-data reproduce-mgp6 reproduce-longmemeval figures paper thesis clean repo-check

setup:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e '.[dev]'

test:
	$(PYTEST) -q

test-fast:
	$(PYTEST) -q -m 'not slow and not network'

lint:
	ruff check src tests scripts benchmarks

format:
	ruff format src tests scripts benchmarks

typecheck:
	mypy --follow-imports=skip src/ksa/controller src/ksa/memory src/ksa/eval/mgp6.py src/ksa/eval/mgp6_schema.py

build:
	$(PYTHON) -m build

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

thesis:
	@echo 'Thesis source is under thesis/. Institutional metadata remains explicit placeholders.'

repo-check:
	$(PYTHON) scripts/validate_repository.py

clean:
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
