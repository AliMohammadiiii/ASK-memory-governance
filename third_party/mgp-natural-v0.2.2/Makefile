PYTHON ?= python
PIP ?= $(PYTHON) -m pip
export PYTHONPATH := $(CURDIR)/src
STUDYCHAT_ARCHIVE ?= .private/source/studychat_audit.zip
AUDIT_DIR ?= .private/audit/studychat
CANDIDATE_INPUT ?= $(AUDIT_DIR)/studychat_audit/mgp_candidate_sample.jsonl
LONG_INPUT ?= $(AUDIT_DIR)/studychat_audit/long_chat_sample.jsonl
PRIVATE_DERIVED ?= .private/derived
PACKET_SECRET ?= .private/packets/studychat/blinding_secret.bin
WHEEL ?= dist/mgp_natural-0.2.2-py3-none-any.whl
FULL_WIKICONV_MAX_PER_ACTION_YEAR ?= 250

.PHONY: install check execution-summary test lint typecheck offline-static toolchain-audit private-permissions private-inventory security-scan build build-reproducibility audit-input ingest-studychat acquire-wikiconv reconstruct mine validate-candidates privacy-scan continuity-audit build-splits build-private-packets verify-private-packets validate-annotations validate-adjudications build-gold score claim-check claim-check-legacy claim-check-full readiness readiness-legacy readiness-full package-public clean-reproduce reproduce full-audit-input full-reconstruct-studychat full-scan-wikiconv full-context-wikiconv full-privacy-blind annotate-ai-provisional full-continuity-splits full-validate paper-full full-reproduce package-workproduct

install:
	$(PIP) install -e '.[dev]'

check: test lint typecheck offline-static toolchain-audit private-permissions private-inventory security-scan build claim-check readiness

lint:
	$(PYTHON) scripts/run_named_check.py --name ruff --output reports/ruff.json -- $(PYTHON) -m ruff check src scripts tests

typecheck:
	$(PYTHON) scripts/run_named_check.py --name mypy --output reports/mypy.json -- $(PYTHON) -m mypy src/mgp_natural

test:
	$(PYTHON) scripts/run_tests.py

offline-static:
	$(PYTHON) scripts/offline_static_checks.py --root . --output reports/offline_static_checks.json

toolchain-audit:
	$(PYTHON) scripts/audit_toolchain.py --output reports/ENVIRONMENT_TOOLCHAIN.json

private-permissions:
	$(PYTHON) scripts/audit_private_permissions.py --private-root .private --output reports/private_permissions.json --repair

private-inventory:
	$(PYTHON) scripts/generate_private_inventory.py --root . --output release/PRIVATE_FILE_INVENTORY.json

security-scan:
	$(PYTHON) scripts/scan_repository_security.py --root . --output reports/security_scan.json

build:
	$(PYTHON) scripts/build_artifacts.py --root . --output reports/build_artifacts.json

build-reproducibility:
	$(PYTHON) scripts/verify_build_reproducibility.py --root . --build-report reports/build_artifacts.json --output reports/build_reproducibility.json

# -----------------------------------------------------------------------------
# Full-source private pipeline. Raw source files are read only from
# $$MGP_FULL_INPUTS and are never copied into the repository or public packages.
# -----------------------------------------------------------------------------
full-audit-input:
	$(PYTHON) scripts/full_sources.py audit --repo-root .

full-reconstruct-studychat:
	$(PYTHON) scripts/full_sources.py reconstruct-studychat --repo-root .

full-scan-wikiconv:
	$(PYTHON) scripts/full_sources.py scan-wikiconv --repo-root . --max-per-action-year $(FULL_WIKICONV_MAX_PER_ACTION_YEAR)

full-context-wikiconv:
	$(PYTHON) scripts/full_sources.py context-wikiconv --repo-root .

full-privacy-blind:
	$(PYTHON) scripts/full_sources.py privacy-blind --repo-root .

annotate-ai-provisional:
	$(PYTHON) scripts/annotate_ai_provisional_full.py --repo-root .

full-continuity-splits:
	$(PYTHON) scripts/full_continuity_splits.py --repo-root .

full-validate:
	$(PYTHON) scripts/validate_full.py --repo-root .

paper-full:
	@test -f paper/main_anonymous.tex
	@test -f paper/main_nonanonymous.tex
	@test -f paper/AI_USE_STATEMENT.md
	@echo PAPER_SCAFFOLD_PRESENT_HUMAN_GOLD_AND_RELEASE_GATES_PENDING

claim-check-full:
	$(PYTHON) scripts/generate_claims_full.py --repo-root .
	$(PYTHON) scripts/verify_claims.py --ledger claims/claim_ledger_full.yaml --documents reports/EXECUTION_SUMMARY_FULL.md paper/CLAIM_BOUNDARY_UPDATED.md paper/RESULT_STATUS_UPDATED.md --output claims/mismatch_report_full.json

readiness-full:
	$(PYTHON) scripts/readiness_full.py --repo-root .

full-reproduce: full-audit-input full-reconstruct-studychat full-scan-wikiconv full-context-wikiconv full-privacy-blind annotate-ai-provisional full-continuity-splits full-validate test lint typecheck build paper-full claim-check-full readiness-full private-permissions private-inventory security-scan
	@echo MGP_NATURAL_FULL_PRIVATE_DERIVATION_COMPLETE_HUMAN_GATES_PENDING

# -----------------------------------------------------------------------------
# Legacy sample-derivative pipeline retained for historical reproducibility.
# -----------------------------------------------------------------------------
audit-input:
	$(PYTHON) scripts/audit_input.py --archive $(STUDYCHAT_ARCHIVE) --extract-dir $(AUDIT_DIR) --output reports/runtime_input_audit.json

ingest-studychat:
	$(PYTHON) scripts/ingest_studychat.py --output-dir data/raw/studychat

acquire-wikiconv:
	$(PYTHON) scripts/acquire_wikiconv.py --manifest reports/wikiconv_source_manifest.json --access-date 2026-08-04 --attempt-report reports/WIKICONV_ACQUISITION_ATTEMPT.json

reconstruct:
	mkdir -p $(PRIVATE_DERIVED)
	chmod 700 $(PRIVATE_DERIVED)
	$(PYTHON) scripts/reconstruct_studychat.py --candidate-input $(CANDIDATE_INPUT) --long-input $(LONG_INPUT) --output $(PRIVATE_DERIVED)/studychat_available_chats.jsonl --anomalies $(PRIVATE_DERIVED)/studychat_available_reconstruction_anomalies.jsonl --report reports/studychat_reconstruction.json
	$(PYTHON) scripts/reconstruct_wikiconv.py --input data/fixtures/wikiconv_actions.jsonl --output $(PRIVATE_DERIVED)/wikiconv_fixture_reconstructed.jsonl

mine:
	mkdir -p $(PRIVATE_DERIVED)
	chmod 700 $(PRIVATE_DERIVED)
	$(PYTHON) scripts/mine_candidates.py --track studychat --input-format reconstructed_chats --input $(PRIVATE_DERIVED)/studychat_available_chats.jsonl --candidates $(PRIVATE_DERIVED)/studychat_candidates.jsonl --rejections $(PRIVATE_DERIVED)/studychat_rejections.jsonl --report reports/studychat_candidate_yield.json
	$(PYTHON) scripts/mine_candidates.py --track wikiconv --input $(PRIVATE_DERIVED)/wikiconv_fixture_reconstructed.jsonl --candidates $(PRIVATE_DERIVED)/wikiconv_fixture_candidates.jsonl --report reports/wikiconv_fixture_candidate_yield.json

validate-candidates:
	$(PYTHON) scripts/validate_candidates.py --input $(PRIVATE_DERIVED)/studychat_candidates.jsonl --schema schemas/construction_item.schema.json

privacy-scan:
	$(PYTHON) scripts/scan_privacy.py --input $(PRIVATE_DERIVED)/studychat_candidates.jsonl --findings $(PRIVATE_DERIVED)/studychat_privacy_findings.jsonl --report reports/PII_SCAN.json --queue reports/MANUAL_PRIVACY_REVIEW_QUEUE.csv --redacted $(PRIVATE_DERIVED)/studychat_candidates_redacted.jsonl --redaction-log $(PRIVATE_DERIVED)/studychat_redaction_log.jsonl --redaction-summary reports/studychat_redaction_summary.json

continuity-audit:
	$(PYTHON) scripts/build_continuity_graph.py --input $(PRIVATE_DERIVED)/studychat_candidates_redacted.jsonl --assignments $(PRIVATE_DERIVED)/studychat_components.jsonl --report reports/studychat_continuity.json

build-splits:
	$(PYTHON) scripts/build_splits.py --items $(PRIVATE_DERIVED)/studychat_candidates_redacted.jsonl --components $(PRIVATE_DERIVED)/studychat_components.jsonl --manifest manifests/studychat_split_private.jsonl --report reports/studychat_split_audit.json

build-private-packets:
	@if [ -f "$(PACKET_SECRET)" ]; then \
		$(PYTHON) scripts/build_private_packet.py --input $(PRIVATE_DERIVED)/studychat_candidates_redacted.jsonl --private-dir .private/packets/studychat --packet .private/packets/studychat_annotation.zip --commitment manifests/studychat_mapping_commitment.json --secret-file $(PACKET_SECRET); \
	else \
		$(PYTHON) scripts/build_private_packet.py --input $(PRIVATE_DERIVED)/studychat_candidates_redacted.jsonl --private-dir .private/packets/studychat --packet .private/packets/studychat_annotation.zip --commitment manifests/studychat_mapping_commitment.json; \
	fi

verify-private-packets:
	$(PYTHON) scripts/verify_private_packet.py --packet .private/packets/studychat_annotation.zip --output reports/private_packet_verification.json

validate-annotations:
	$(PYTHON) scripts/validate_annotations.py --items data/fixtures/blind_items.jsonl --annotations data/fixtures/annotations_valid.jsonl --report reports/fixture_annotation_validation.json --agreement reports/fixture_agreement.json

validate-adjudications:
	$(PYTHON) scripts/validate_adjudications.py --items data/fixtures/blind_items.jsonl --annotations data/fixtures/annotations_valid.jsonl --adjudications data/fixtures/adjudications_valid.jsonl --report reports/fixture_adjudication_validation.json

build-gold:
	$(PYTHON) scripts/build_gold.py --items .private/packets/studychat/bundle/items.jsonl --adjudications .private/adjudications/studychat.jsonl --approvals manifests/human_approvals.json --output .private/gold/studychat.jsonl

score:
	$(PYTHON) scripts/score_predictions.py --gold data/fixtures/provisional_gold.jsonl --predictions data/fixtures/predictions.jsonl --output reports/provisional_smoke_score.json --allow-provisional-smoke

execution-summary:
	$(PYTHON) scripts/generate_execution_summary.py --root . --output reports/EXECUTION_SUMMARY.json --markdown reports/EXECUTION_SUMMARY.md

claim-check-legacy:
	$(PYTHON) scripts/verify_claims.py --ledger claims/claim_ledger.yaml --documents README.md docs/DATASET_CARD.md paper/main.tex paper/CLAIM_BOUNDARY.md --output claims/mismatch_report.json

readiness-legacy:
	$(PYTHON) scripts/readiness.py --status manifests/gate_status.json --output reports/readiness.json --go-no-go reports/GO_NO_GO.md --remaining-actions reports/REMAINING_EXTERNAL_ACTIONS.md

claim-check:
	@if [ -f reports/INPUT_INVENTORY_FULL.json ]; then \
		$(MAKE) claim-check-full; \
	else \
		$(MAKE) claim-check-legacy; \
	fi

readiness:
	@if [ -f reports/INPUT_INVENTORY_FULL.json ]; then \
		$(MAKE) readiness-full; \
	else \
		$(MAKE) readiness-legacy; \
	fi

package-public:
	$(PYTHON) scripts/package_public.py --root . --approvals manifests/human_approvals.json --output release/mgp-natural-public.zip --inventory release/PUBLIC_FILE_INVENTORY.json --report reports/package_public_attempt.json

clean-reproduce:
	@test -f "$(WHEEL)" || { echo "MISSING_BUILT_WHEEL_RUN_MAKE_BUILD"; exit 2; }
	$(PYTHON) scripts/clean_reproduce.py --root . --wheel $(WHEEL) --output reports/clean_reproduction.json

reproduce: audit-input acquire-wikiconv reconstruct mine validate-candidates privacy-scan continuity-audit build-splits build-private-packets verify-private-packets private-permissions private-inventory security-scan validate-annotations validate-adjudications score readiness-legacy execution-summary claim-check-legacy
	@echo MGP_NATURAL_LEGACY_SAMPLE_DERIVATION_COMPLETE_WITH_RECORDED_GATES

package-workproduct:
	@echo Use the supplied packaging script outside the repository; raw and .private files must remain excluded.

