# Reproducibility Checklist

Date: 2026-07-12. NeurIPS/ACL-style checklist answered **honestly for the current
state**. Answers: **Yes** / **Partial** / **No** / **Pending**. Every "Yes"
points at an artifact; every "Partial/Pending" names exactly what is missing.

---

## 1. Code

| Item | Answer | Evidence / caveat |
|---|---|---|
| Is the controller/model code released? | **Yes** | `src/ask/` (controller, memory, extraction, inference, baselines, evaluation). |
| Are baselines released? | **Yes** | no-memory, flat-vector, recency, naive-overwrite in `src/ask/baselines/`. |
| Is the scoring code released? | **Yes** | `mgp6_v2/metrics_mgp6.py` (MGP-6); `src/ask/eval/longmemeval.py` (LME). |
| Are the analysis scripts released? | **Yes** | `scripts/analysis/mcnemar_mgp6.py` (this layer), `build_final_results.py`, `analyze_single_session_preferences.py`, `build_v8_adjudicated_report.py`. |
| Is there a test suite? | **Yes** | README: 420 passing tests + 14 documented skips; scorer-regression + failure-regression tests (e.g. `test_extractor_recovery.py`, `test_cascade_escalation.py`, `test_relation_classifier.py`, `test_scoring.py`). |
| Is there CI? | **Yes** | `.github/workflows/ci.yml`. |
| Is there a build/repro entry point? | **Yes** | `Makefile` (`make setup / repo-check / test / validate-data / build`). |

## 2. Data

| Item | Answer | Evidence / caveat |
|---|---|---|
| Is the primary dataset included? | **Partial** | **MGP-6 v2 included** (`benchmarks/mgp6/data/mgp6_v2.jsonl`, 180 items, checksummed in `artifacts/manifests/`). |
| Is the second dataset included? | **No (by policy)** | **LongMemEval-M is external**; not redistributed (`ledger.longmemeval_m.dataset.redistribution`). Only run outputs / judgments are referenced. |
| Is the data schema documented? | **Yes** | `mgp6_v2/mgp6_schema_v2.py`, `schema/` (LinkML/SQL/JSON), `mgp6_v2/dataset_card.md`. |
| Are train/dev/test splits fixed and documented? | **Yes** | 60/30/90 stratified by type; recorded in the ledger and dataset. |
| Are the per-item predictions available? | **Yes (MGP-6)** | `artifacts/mgp6_v2/*/predictions.jsonl` (180 lines each). LME judgments under the run dirs (external run tree). |

## 3. Experimental setup

| Item | Answer | Evidence / caveat |
|---|---|---|
| Are models/versions specified? | **Yes** | main `qwen/qwen3.5-9b`; judge `google/gemma-4-31b-it(:free)`; external adapters versioned (mem0 2.0.11, graphiti 0.29.2, Letta/MemGPT, MemOS). `configs/models/openrouter_qwen_gemma.yaml`. |
| Are hyperparameters/configs released? | **Yes** | `configs/` (controller, experiments, model config). |
| Is the frozen evaluation protocol documented? | **Partial** | `FINAL_EVALUATION_PROTOCOL.md` / `configs/release/final.yaml` exist; the homogeneous LME rerun under it is **Pending** (not executed). |

## 4. Randomness / seeds

| Item | Answer | Evidence / caveat |
|---|---|---|
| Are seeds fixed and reported? | **Yes** | LME slice seed 0; MGP-6 bootstrap seed 62026/62027 (`metrics_mgp6.py`); SSP bootstrap n=20000 seed 0; McNemar bootstrap n=10000 seed 20260712; v8 adjudicated build n_bootstrap=10000 seed 20260710. |
| Multiple seeds / run-to-run variance? | **No** | Single seed per track; SSP CI reflects item sampling only, not run variance. **Open.** |

## 5. Uncertainty / statistics

| Item | Answer | Evidence / caveat |
|---|---|---|
| Are confidence intervals reported? | **Yes, where valid** | Wilson + Newcombe + bootstrap CIs for MGP-6; v7 SSP diagnostic CI [0.20, 0.53]; annotation κ CIs. The historical 77.2% interval is explicitly rejected as inference for a complete v8 run. |
| Are significance tests reported with multiplicity control? | **Yes (MGP-6)** | Exact McNemar + Holm across the 4-test family. **None on LongMemEval** (diagnostic only, by policy). |
| Are effect sizes reported? | **Yes** | Risk differences + McNemar odds ratios. |

## 6. Compute

| Item | Answer | Evidence / caveat |
|---|---|---|
| Is compute described? | **Partial** | Runs used OpenRouter (v7) and Modal-hosted Qwen (v8 replay); shared MiniLM embedding server; `--embedder-device cpu`. Exact GPU-hours/cost not tabulated. **Open**: a compute table is not yet produced. |
| Are provider/runtime conditions disclosed? | **Yes (as failures)** | v7 HTTP-402 exhaustion (316), ≥12 relaunches, escalation no-op documented in the failure ledger. |

## 7. Licensing / ethics

| Item | Answer | Evidence / caveat |
|---|---|---|
| Is the code license present? | **Yes** | `LICENSE`. |
| Is the data license present? | **Yes** | `LICENSE-DATA.md` (MGP-6). |
| Is external-data licensing respected? | **Yes** | LongMemEval not redistributed; integration contract only (`benchmarks/longmemeval/`). |
| Security / credential hygiene documented? | **Yes** | `SECURITY.md`; README instructs key rotation; no embedded credentials. **Action item**: rotate the previously-exposed OpenRouter key before release. |

## 8. Claims vs evidence

| Item | Answer | Evidence / caveat |
|---|---|---|
| Are claim-eligibility labels attached to every result? | **Yes** | Ledger + `FINAL_RESULTS.md/json`; `CLAIMS_EVIDENCE_MATRIX.md`. |
| Are invalid/superseded runs quarantined? | **Yes** | `docs/audit/INVALID_AND_SUPERSEDED_RUNS.md`. |
| Is a manifest/provenance chain present? | **Partial** | `artifacts/manifests/` checksums; **but** the v8 adjudicated `manifest.json` records a non-existent `replay_run` path (failure ledger F11) — the manifest is not a runnable recipe as written. |

---

## Pending items (explicit)

1. **Pending** — homogeneous full-180 LongMemEval rerun under the frozen v8 config
   (single primary judge, prepaid credit). Blocks every final LME claim.
2. **Pending** — complete pre-specified few-shot (6-shot) MGP-6 run. The 174
   observed predictions have been coverage-aligned with six `INVALID` rows, but
   the source run remains incomplete.
3. **Pending** — full 500-item LongMemEval evaluation.
4. **Pending** — role-separated MGP-6 v3 construction and hidden confirmation;
   a family holdout over v2 cannot repair the persistent label shortcut.
5. **Pending** — three blinded human annotators and independent adjudication for v3.
6. **Pending** — multi-seed / multi-base-model runs; compute (GPU-hours/cost) table.
7. **Fix-before-release** — correct the v8 adjudicated `manifest.json` `replay_run`
   path (F11); rotate the exposed API key; replace `OWNER` placeholders.
