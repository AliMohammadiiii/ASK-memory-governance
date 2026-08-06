PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,$(shell command -v python3.12 2>/dev/null || command -v python3.11 2>/dev/null || command -v python3 2>/dev/null))
PYTEST ?= $(PYTHON) -m pytest
RUFF ?= $(PYTHON) -m ruff
MYPY ?= $(PYTHON) -m mypy
MAINTAINED_PYTHON := src tests scripts benchmarks deploy/download_longmemeval_s.py thesis/latex/tools
MGP_NATURAL_ARCHIVE ?=
MGP_NATURAL_DELIVERY_REPORT ?=
MGP_NATURAL_RESEARCH_REPORT ?=
MGP_NATURAL_PRIVATE_DIR ?= .private/mgp_natural/v0.1.0
MGP_NATURAL_DERIVED_MANIFEST ?= artifacts/manifests/mgp_natural_v0_1_1_derived_audit.json
MGP_NATURAL_FULL_INPUTS ?=
MGP_NATURAL_FULL_INTAKE_AUDIT ?= confirmation/natural_challenge/mgp_natural_v0_2_2_full/intake_audit.json
MGP_NATURAL_V022_PYTHON = $(if $(findstring /,$(PYTHON)),$(abspath $(PYTHON)),$(PYTHON))

.DEFAULT_GOAL := help

.PHONY: help setup setup-ml setup-external hf-compat check release-check test test-fast lint format format-check \
	typecheck build shell-syntax compile smoke validate-data reproduce-mgp6 \
	reproduce-longmemeval figures paper paper-audit thesis clean repo-check \
	manuscript-check thesis-template \
	specialist-locks \
	claims verify-claims inventory verify-manifest readiness validate-traces \
	validate-public-data reproduce-public build-paper-tmlr build-paper-jmlr \
	anonymous-scan release-audit ci clean-reproduction validate-experiments \
	verify-paper-artifacts confirmation-authoring-package confirmation-dry-run \
	confirmation-freeze confirmation-predict confirmation-unseal confirmation-score \
	mgpn-natural-audit mgpn-natural-manifest mgpn-natural-dry-run mgpn-natural-build-private \
	mgpn-natural-verify-private mgpn-natural-package-public mgpn-natural-full-intake \
	mgpn-natural-v022-test advisor-check advisor-package advisor-clean prompt-check \
	prose-check document-check cleanup-inventory pre-commit

help:
	@echo "setup          Install the package and development tools"
	@echo "setup-ml       Install the maintained ML stack from its Python 3.12 lock"
	@echo "setup-external Install external adapters from their isolated Python 3.12 lock"
	@echo "hf-compat      Verify locked Hugging Face versions and hermetic integration contracts"
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
	@echo "mgpn-natural-audit  Audit the pinned external MGP-Natural candidate ZIP"
	@echo "mgpn-natural-manifest  Pin parent/report hashes and derived anomaly lineage"
	@echo "mgpn-natural-dry-run  Test MGP-Natural blinding, annotation, and scorer guards"
	@echo "mgpn-natural-build-private  Build a private, non-distributable annotation draft"
	@echo "mgpn-natural-verify-private  Reproduce and verify the private draft and commitment"
	@echo "mgpn-natural-package-public  Block public packaging until human/legal and gold gates pass"
	@echo "mgpn-natural-full-intake  Audit external StudyChat and WikiConv inputs without importing them"
	@echo "mgpn-natural-v022-test  Run the vendored MGP-Natural v0.2.2 software tests"
	@echo "advisor-check  Run the offline, privacy-safe supervisor review gate"
	@echo "advisor-package  Build a sanitized local supervisor review snapshot"
	@echo "paper           Compile the complete canonical paper"
	@echo "thesis          Compile the complete canonical thesis"
	@echo "specialist-locks  Validate exact specialist dependency locks"
	@echo "advisor-clean  Remove only generated supervisor review outputs"
	@echo "prompt-check  Validate prompt registry metadata and hashes"
	@echo "prose-check  Reject strong generated-text leakage in maintained prose"
	@echo "document-check  Validate maintained Markdown and LaTeX file references"
	@echo "cleanup-inventory  Regenerate the repository cleanup inventory"
	@echo "pre-commit  Run all pinned local hooks"

setup:
	@if git rev-parse --git-dir >/dev/null 2>&1; then \
		git submodule update --init --recursive; \
	fi
	@if [ ! -x .venv/bin/python ]; then \
		$(PYTHON) -m venv .venv; \
	fi
	.venv/bin/python -m pip install -U pip
	.venv/bin/python -m pip install -e '.[dev]'

setup-ml:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e '.[dev,ml]' -c constraints/ml-py312.txt

setup-external:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -r benchmarks/mgp6/external/requirements-external.txt \
		-c constraints/external-baselines-py312.txt

hf-compat:
	$(PYTHON) scripts/validation/validate_huggingface_environment.py
	$(PYTEST) -q tests/test_llm.py tests/test_embeddings.py \
		tests/test_nextgen_thinking_embedder.py tests/test_judge_backend.py \
		tests/test_m4w13_hf_runner.py tests/test_release_tooling.py tests/test_rejudge.py

check: repo-check prompt-check prose-check document-check lint format-check typecheck compile \
	test-fast shell-syntax

release-check: check test validate-data build paper-audit manuscript-check specialist-locks

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

manuscript-check:
	$(PYTHON) scripts/validation/build_manuscripts.py --check

specialist-locks:
	$(PYTHON) scripts/validation/validate_specialist_environment.py --profile ml --lock-only
	$(PYTHON) scripts/validation/validate_specialist_environment.py --profile adapters --lock-only

paper: manuscript-check
	$(PYTHON) scripts/validation/build_manuscripts.py --kind paper

paper-audit:
	$(PYTHON) scripts/analysis/audit_mgp6_validity.py
	$(PYTHON) scripts/release/audit_bibliography.py

thesis-template:
	git submodule update --init --recursive thesis/template

thesis: manuscript-check thesis-template
	$(PYTHON) scripts/validation/build_manuscripts.py --kind thesis

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

mgpn-natural-audit:
	@test -n "$(MGP_NATURAL_ARCHIVE)" || { echo 'Set MGP_NATURAL_ARCHIVE to the pinned parent ZIP'; exit 2; }
	$(PYTHON) scripts/confirmation/prepare_mgpn_candidate.py \
		--archive "$(MGP_NATURAL_ARCHIVE)" \
		--audit-report confirmation/natural_challenge/mgp_natural_v0_1_0/archive_audit.json

mgpn-natural-manifest: mgpn-natural-audit
	@test -n "$(MGP_NATURAL_DELIVERY_REPORT)" || { echo 'Set MGP_NATURAL_DELIVERY_REPORT to the supplied delivery report'; exit 2; }
	@test -n "$(MGP_NATURAL_RESEARCH_REPORT)" || { echo 'Set MGP_NATURAL_RESEARCH_REPORT to the supplied research report'; exit 2; }
	$(PYTHON) scripts/provenance/build_mgpn_derived_manifest.py \
		--archive "$(MGP_NATURAL_ARCHIVE)" \
		--delivery-report "$(MGP_NATURAL_DELIVERY_REPORT)" \
		--research-report "$(MGP_NATURAL_RESEARCH_REPORT)" \
		--audit-report confirmation/natural_challenge/mgp_natural_v0_1_0/archive_audit.json \
		--output "$(MGP_NATURAL_DERIVED_MANIFEST)"

mgpn-natural-dry-run:
	$(PYTEST) -q tests/test_confirmation_protocol.py tests/test_mgpn_confirmation.py \
		tests/test_mgpn_manifest.py tests/test_mgpn_source_matrix.py

mgpn-natural-build-private: mgpn-natural-dry-run
	@test -n "$(MGP_NATURAL_ARCHIVE)" || { echo 'Set MGP_NATURAL_ARCHIVE to the pinned parent ZIP'; exit 2; }
	$(PYTHON) scripts/confirmation/prepare_mgpn_candidate.py \
		--archive "$(MGP_NATURAL_ARCHIVE)" \
		--audit-report confirmation/natural_challenge/mgp_natural_v0_1_0/archive_audit.json \
		--packet "$(MGP_NATURAL_PRIVATE_DIR)/blind_packet.jsonl" \
		--answers "$(MGP_NATURAL_PRIVATE_DIR)/annotation_form.csv" \
		--private-map "$(MGP_NATURAL_PRIVATE_DIR)/private_mapping.json" \
		--commitment "$(MGP_NATURAL_PRIVATE_DIR)/packet_commitment.json" \
		--safe-summary "$(MGP_NATURAL_PRIVATE_DIR)/safe_summary.json" \
		--bundle "$(MGP_NATURAL_PRIVATE_DIR)/MGP-Natural-v0.1.0-draft-annotation-packet.zip" \
		--write-private

mgpn-natural-verify-private:
	@test -n "$(MGP_NATURAL_ARCHIVE)" || { echo 'Set MGP_NATURAL_ARCHIVE to the pinned parent ZIP'; exit 2; }
	$(PYTHON) scripts/confirmation/verify_mgpn_candidate.py \
		--archive "$(MGP_NATURAL_ARCHIVE)" \
		--packet "$(MGP_NATURAL_PRIVATE_DIR)/blind_packet.jsonl" \
		--answers "$(MGP_NATURAL_PRIVATE_DIR)/annotation_form.csv" \
		--private-map "$(MGP_NATURAL_PRIVATE_DIR)/private_mapping.json" \
		--commitment "$(MGP_NATURAL_PRIVATE_DIR)/packet_commitment.json" \
		--bundle "$(MGP_NATURAL_PRIVATE_DIR)/MGP-Natural-v0.1.0-draft-annotation-packet.zip" \
		--output confirmation/natural_challenge/mgp_natural_v0_1_0/private_packet_verification.json

mgpn-natural-package-public:
	@echo 'BLOCKED_PENDING_HUMAN_LEGAL_PRIVACY_APPROVAL_AND_INDEPENDENT_GOLD'; exit 1

mgpn-natural-full-intake:
	@test -n "$(MGP_NATURAL_FULL_INPUTS)" || { echo 'Set MGP_NATURAL_FULL_INPUTS to the private v0.2.2 source directory'; exit 2; }
	$(PYTHON) scripts/confirmation/audit_mgpn_full_inputs.py \
		--input-root "$(MGP_NATURAL_FULL_INPUTS)" \
		--output "$(MGP_NATURAL_FULL_INTAKE_AUDIT)"

mgpn-natural-v022-test:
	cd third_party/mgp-natural-v0.2.2 && PYTHONPATH=src $(MGP_NATURAL_V022_PYTHON) -m pytest -q tests

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

advisor-clean:
	$(PYTHON) scripts/release/build_advisor_handoff.py --clean

prompt-check:
	$(PYTHON) scripts/validation/validate_prompt_registry.py

prose-check:
	$(PYTHON) scripts/validation/validate_prose_hygiene.py

document-check:
	$(PYTHON) scripts/validation/validate_document_paths.py

cleanup-inventory:
	$(PYTHON) scripts/research/build_repository_cleanup_inventory.py

pre-commit:
	$(PYTHON) -m pre_commit run --all-files

clean-reproduction:
	$(PYTHON) scripts/reproduction/run_clean_reproduction.py

ci: check validate-public-data validate-traces validate-experiments \
	verify-paper-artifacts readiness

clean: advisor-clean
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache htmlcov
	rm -rf paper/paper_1/compiled thesis/latex/compiled
	rm -rf third_party/mgp-natural-v0.2.2/.pytest_cache \
		third_party/mgp-natural-v0.2.2/.ruff_cache \
		third_party/mgp-natural-v0.2.2/.mypy_cache
	rm -f .coverage
	find src tests scripts benchmarks -type d -name __pycache__ -prune -exec rm -rf {} +
	@if [ -d third_party/mgp-natural-v0.2.2 ]; then \
		find third_party/mgp-natural-v0.2.2 -type d -name __pycache__ -prune -exec rm -rf {} +; \
	fi
	@if command -v latexmk >/dev/null 2>&1; then \
		cd thesis/template && latexmk -C -jobname=ask_thesis ../latex/main.tex >/dev/null; \
	fi
