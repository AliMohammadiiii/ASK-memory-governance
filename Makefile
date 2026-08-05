PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest
RUFF ?= $(PYTHON) -m ruff
MYPY ?= $(PYTHON) -m mypy
MAINTAINED_PYTHON := src tests scripts benchmarks deploy/download_longmemeval_s.py thesis/latex/tools

.DEFAULT_GOAL := help

.PHONY: help setup check release-check test test-fast lint format format-check \
	typecheck build shell-syntax compile smoke validate-data reproduce-mgp6 \
	reproduce-longmemeval figures paper paper-audit thesis clean repo-check \
	claims verify-claims inventory verify-manifest readiness validate-traces \
	validate-public-data reproduce-public build-paper-tmlr build-paper-jmlr \
	anonymous-scan release-audit ci clean-reproduction validate-experiments \
	verify-paper-artifacts confirmation-authoring-package confirmation-dry-run \
	confirmation-freeze confirmation-predict confirmation-unseal confirmation-score \
	advisor-check advisor-package

help:
	@echo "setup          Install the package and development tools"
	@echo "check          Run the fast, offline development gate"
	@echo "release-check  Run the complete offline release gate"
	@echo "test           Run the complete test suite"
	@echo "lint           Run Ruff lint checks"
	@echo "format         Format maintained Python code"
	@echo "typecheck      Run the supported mypy scope"
	@echo "build          Build sdist and wheel"
	@echo "claims         Recompute the private-evidence claim ledger"
	@echo "verify-claims  Verify the committed claim ledger and mismatches"
	@echo "inventory      Regenerate the artifact/source inventory"
	@echo "readiness      Generate the mandatory publication GO/NO-GO report"
	@echo "release-audit  Run release-boundary and anonymity checks"
	@echo "clean-reproduction  Verify the public path in a fresh venv from a clean commit"
	@echo "validate-experiments  Validate the prospective no-execution model matrix"
	@echo "verify-paper-artifacts  Check headline LaTeX fragments for numeric drift"
	@echo "confirmation-dry-run  Validate confirmation schemas and blind-packet safeguards"
	@echo "confirmation-freeze  Freeze only after independent human/legal approval"
	@echo "advisor-check  Run the offline, privacy-safe supervisor review gate"
	@echo "advisor-package  Build a sanitized local supervisor review snapshot"

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
	$(RUFF) check $(MAINTAINED_PYTHON)

format:
	$(RUFF) format $(MAINTAINED_PYTHON)
	$(RUFF) check --fix $(MAINTAINED_PYTHON)

format-check:
	$(RUFF) format --check $(MAINTAINED_PYTHON)

typecheck:
	$(MYPY) src/ask

build:
	$(PYTHON) -m build
	$(PYTHON) scripts/release/verify_wheel.py --dist-dir dist

shell-syntax:
	git ls-files -z '*.sh' | xargs -0 bash -n

compile:
	$(PYTHON) -m compileall -q $(MAINTAINED_PYTHON)

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

claims:
	$(PYTHON) scripts/claims/build_claim_ledger.py

verify-claims:
	$(PYTHON) scripts/claims/verify_claims.py

inventory:
	$(PYTHON) scripts/research/build_artifact_inventory.py

verify-manifest:
	$(PYTHON) scripts/provenance/verify_lme_v12_derived_manifest.py

readiness:
	$(PYTHON) scripts/check_readiness.py

validate-traces:
	$(PYTHON) scripts/validation/validate_ask_traces.py
	$(PYTEST) -q tests/test_ask_protocol.py

validate-public-data:
	$(PYTHON) scripts/release/validate_public_data.py

validate-experiments:
	$(PYTHON) scripts/experiments/validate_model_matrix.py

verify-paper-artifacts:
	$(PYTHON) scripts/paper/verify_generated_outputs.py

confirmation-authoring-package:
	$(PYTEST) -q tests/test_confirmation_protocol.py

confirmation-dry-run: confirmation-authoring-package
	@echo 'PASS_DRY_RUN: no labels, prediction, unsealing, or paid inference executed'

confirmation-freeze:
	$(PYTHON) scripts/confirmation/freeze_protocol.py \
		--out confirmation/frozen_configs/protocol_commitment.json

confirmation-predict:
	@echo 'BLOCKED_PENDING_FROZEN_MATRIX_AND_EXPLICIT_EXECUTION_AUTHORIZATION'; exit 1

confirmation-unseal:
	@echo 'BLOCKED_PENDING_INDEPENDENT_ANNOTATION_AND_ONE_TIME_HUMAN_AUTHORIZATION'; exit 1

confirmation-score:
	@echo 'BLOCKED_PENDING_AUTHORIZED_UNSEAL'; exit 1

reproduce-public: repo-check test lint format-check typecheck validate-data \
	validate-public-data validate-traces validate-experiments verify-paper-artifacts

build-paper-tmlr:
	@test -f paper/tmlr/main.tex || { echo 'BLOCKED: canonical TMLR source is not in paper/tmlr'; exit 1; }
	cd paper/tmlr && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

build-paper-jmlr:
	@test -f paper/jmlr/main.tex || { echo 'BLOCKED: canonical JMLR source is not in paper/jmlr'; exit 1; }
	cd paper/jmlr && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

anonymous-scan:
	$(PYTHON) scripts/release/anonymous_scan.py

release-audit: verify-claims verify-manifest validate-public-data anonymous-scan readiness

advisor-check: check verify-claims verify-manifest validate-public-data \
	validate-traces validate-experiments verify-paper-artifacts anonymous-scan readiness

advisor-package: advisor-check
	$(PYTHON) scripts/release/build_advisor_handoff.py --replace

clean-reproduction:
	$(PYTHON) scripts/reproduction/run_clean_reproduction.py

ci: check validate-public-data validate-traces validate-experiments \
	verify-paper-artifacts readiness

clean:
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache htmlcov
	rm -f .coverage
	find src tests scripts benchmarks -type d -name __pycache__ -prune -exec rm -rf {} +
