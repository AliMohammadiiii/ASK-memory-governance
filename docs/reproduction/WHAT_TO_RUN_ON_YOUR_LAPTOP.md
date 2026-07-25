# What to run on your laptop (ordered)

Frozen protocol `final-2.0`. This is the exact, ordered command list to take the
ASK final evaluation from a fresh clone to a return package. Every command is
based on an entry point that exists in this repo. **No duration estimates are
given** (they depend on your machine and OpenRouter throughput).

macOS: all wrappers are POSIX/BSD-compatible and use `python3`.

---

## Two hard prerequisites (nothing hosted runs without these)

1. **A valid `OPENROUTER_API_KEY`.** Export it only in your shell; never put a
   key in a tracked file or review package.
2. **LongMemEval-M data present locally** (not redistributable). You need:
   - `LONGMEMEVAL_DATA` -> the full slice jsonl (e.g. `data/slices/longmemeval_m_full.jsonl`)
   - optionally `LONGMEMEVAL_SRC` -> the cleaned source json
     (default `data/longmemeval_m_cleaned.json`), required by the underlying range runner.

The MGP-6 steps and the final-results build are fully offline and need neither.

---

## 0. Setup

```
bash scripts/setup/setup_macos.sh
```
- Purpose: create `.venv` (Python >= 3.11), install the package editable + dev
  extra, scaffold `.env` from `.env.example`, and report key presence.
- Workload: n/a (install only).
- Expected outputs: `.venv/`, `.env` (you fill in the key).
- Success: prints "done"; `CHECK: OPENROUTER_API_KEY is present" once you add the key.
- For real model runs also: `pip install -e '.[ml]'` (torch/sentence-transformers).

## 1. Offline smoke

```
bash scripts/smoke/run_all_smoke_tests.sh
```
- Purpose: fast unit subset + MGP-6 schema validation + 2-item offline MGP-6 dry-run.
- Workload: unit tests; 180-row schema check; 2 scenarios (dry, no models).
- Expected outputs: console PASS lines.
- Success: "ALL OFFLINE SMOKE CHECKS PASSED". No network used.

## 2. Regenerate the locked final results (offline)

```
bash scripts/analysis/build_final_results.sh
```
- Purpose: deterministically rebuild `reports/FINAL_RESULTS.{md,json}` from
  `artifacts/results_ledger.json` (read-only).
- Workload: transcription only.
- Expected outputs: `reports/FINAL_RESULTS.md`, `reports/FINAL_RESULTS.json`.
- Success: both files written; re-running is byte-identical. MGP-6 shows 15
  final-candidate rows; LongMemEval has no final candidate and retains the exact
  `diagnostic_only`, `failure_replay_only`, `incomplete`, `invalid`, and
  `externally_pending` labels.

## 3. MGP-6 final tables: rescore/verify + few-shot recompute (offline)

```
bash scripts/evaluation/run_mgp6_final.sh --full
```
- Purpose: reproduce the locked MGP-6 numbers from archived per-item predictions
  and compute a coverage-aware score for the incomplete 6-shot run (174
  predictions plus six aligned `INVALID` predictions).
- Workload: rescore 8 systems x 180 items (offline; reads `../artifacts/mgp6_v2/...`).
- Expected outputs: `runs_local/mgp6_verify/*_report.json`,
  `runs_local/mgp6_few6_rescore/few6_report.json`.
- Success: rescored `action_accuracy` matches the ledger (e.g. rule controller
  0.9222 / macro-F1 0.9399); few6 reports 0.7833 coverage-aware accuracy and
  remains `incomplete`, not a final-table result.
- Resume: re-run; it refuses to overwrite a non-empty `runs_local/mgp6_verify`
  (move it or remove it to redo).
- Pre-specified MGP-6 significance (McNemar + Holm):
  `python3 scripts/analysis/mcnemar_mgp6.py`

## 4. SSP evaluation on existing outputs (offline, after step 6)

```
bash scripts/evaluation/run_single_session_preferences.sh
```
- Purpose: SSP accuracy + stratified bootstrap CI (n=20000, seed 0) for the
  controller run's preference competency.
- Workload: 30 SSP items.
- Expected outputs: `runs_local/ssp_eval/ssp_*.json`.
- Success: prints SSP accuracy and CI for the selected completed run. The 11/30
  value is only the contaminated v7 diagnostic reference; the incomplete top-up
  observes 8/29 with one unresolved (maximum 9/30).
- NOTE: this reads a completed run's `judgments.jsonl`. Run it after step 6
  (the homogeneous rerun) so it scores the frozen run. Before that it can only
  score archived diagnostic runs.

## 5. Prerequisite check for hosted runs

```
bash scripts/evaluation/run_longmemeval_final.sh --dry-run
```
- Purpose: confirm the frozen command assembles and prints the models/judge in
  use, without calling any model.
- Workload: none (prints plan).
- Success: prints the frozen config (main model qwen/qwen3.5-9b; only judge
  google/gemma-4-31b-it with no model fallback; MiniLM cpu; seed 0)
  and the SAMPLE range; executes nothing.

## 6. Homogeneous LongMemEval-M rerun (HOSTED — the required run)

```
# tiny end-to-end sanity first (hits the API; 2 items):
OPENROUTER_API_KEY=sk-or-... LONGMEMEVAL_DATA=data/slices/longmemeval_m_full.jsonl \
  bash scripts/evaluation/run_longmemeval_final.sh --smoke

# the full run:
OPENROUTER_API_KEY=sk-or-... LONGMEMEVAL_DATA=data/slices/longmemeval_m_full.jsonl \
  bash scripts/evaluation/run_longmemeval_final.sh --full

# controller-only final-candidate run through the identical frozen path:
OPENROUTER_API_KEY=sk-or-... LONGMEMEVAL_DATA=data/slices/longmemeval_m_full.jsonl \
  bash scripts/evaluation/run_longmemeval_final.sh --full --controller-only
```
- Purpose: the frozen full-180, 5-system (controller,b4,b3,b2,b1), one-config,
  one-judge-policy V12 engineering confirmation. Because V11 outcomes informed
  the fixes, this reused-slice run is post-hoc; a new untouched holdout is needed
  to establish a confirmatory final LongMemEval result.
  The 77.2% value is a selection-biased failure-replay construction contradicted
  by the non-empty top-up and is never a result to "replace."
- Workload: `--smoke` = 2 questions; `--full` = 180 questions x 5 systems.
- Controller-only workload: `--full --controller-only` = 180 controller
  questions, written to `runs_local/lme_final_controller_v12_qwen_180`. This is the
  canonical choice when validating the contribution alone; the five-system run
  remains required for a homogeneous comparative table.
- Extraction, relation, and final-answer requests all use Qwen3.5-9B through
  the Venice, DeepInfra, and SiliconFlow pool with reasoning disabled.
- Expected outputs: `runs_local/lme_final_5systems_v12_qwen_180/<system>/{answers,judgments}.jsonl`,
  `.../report.json`, `.../final_summary.json`,
  `.../controller_accuracy_gate.json`, `.../manifest.json`, and `.../logs/`.
- Success: `scripts/verify_homogeneous_run.py` passes (all 180 items per system,
  one judge policy, no patching), and the controller accuracy gate reports at
  least 153/180 (85%). The wrapper exits non-zero if either gate fails.
- Resume: `... bash scripts/evaluation/run_longmemeval_final.sh --resume`
  (continues incomplete shards in place; never rewrites scored items).
- Immutability: without `--resume`, the script refuses to write into a non-empty
  `runs_local/lme_final_5systems_v12_qwen_180` and exits with an error.

## 7. Judge audit (offline, after step 6)

```
bash scripts/evaluation/run_judge_audit.sh runs_local/lme_final_5systems_v12_qwen_180
```
- Purpose: confirm zero model fallback and audit scoring fallbacks.
- Workload: reads all `judgments.jsonl` under the run.
- Expected outputs: `runs_local/judge_audit/lme_final_5systems_v12_qwen_180_judge_audit.json`.
- Success: reports zero model fallback; any deterministic scoring fallback is
  separately visible by competency.

## 8. Ablations (MGP-6 offline; SSP matrix pending)

```
bash scripts/experiments/run_ablations.sh --all
```
- Purpose: rescore MGP-6 controller ablations (full/no_abstain/no_lineage/
  no_provenance/no_typing) from archived predictions; print SSP ablation-matrix
  status.
- Workload: 5 MGP-6 ablations x 180 items (offline).
- Expected outputs: `runs_local/mgp6_ablations/*_report.json`,
  `runs_local/ssp_ablation/STATUS.json`.
- Success: MGP-6 ablation numbers match the ledger (e.g. no_abstain 0.5556,
  no_lineage lineage 0.3689). SSP arms B-G print as
  `pending_external_run_blocked_design` (correction code is PROPOSED only).

## 9. Analysis (pre-specified)

- MGP-6 paired significance (McNemar + Holm across the 4-test family):
  ```
  python3 scripts/analysis/mcnemar_mgp6.py
  ```
- LongMemEval paired comparisons (controller vs b4, controller vs b2) run on the
  step-6 `judgments.jsonl` per `FINAL_ANALYSIS_PLAN.md` (McNemar + paired
  bootstrap + Holm). Do NOT inspect per-item rerun outputs before scoring.

## 10. Package for return

```
bash scripts/release/package_run_for_review.sh runs_local/lme_final_5systems_v12_qwen_180
```
- Purpose: package aggregate reports, manifests, audit summaries, environment
  metadata, and checksums. Raw answers, judgments, prompts, and logs are excluded
  from this public review package by design.
- Expected output: `return_package_lme_final_5systems_v12_qwen_180.tar.gz` at repo root.
- Success: one tarball; credentials excluded; `CHECKSUMS.sha256` + `ENV_REPORT.txt`
  inside.

---

## Files to return

Return, at minimum:
- `return_package_lme_final_5systems_v12_qwen_180.tar.gz` (from step 10), which contains
  the sanitized aggregate run artifacts, `manifest.json`, `ENV_REPORT.txt`, the freeze
  (`configs/release/final.yaml` + `artifacts/manifests/freeze_hashes.json`), and
  `CHECKSUMS.sha256`.
- `runs_local/mgp6_few6_rescore/few6_report.json` (step 3).
- `runs_local/judge_audit/lme_final_5systems_v12_qwen_180_judge_audit.json` (step 7).
- `reports/FINAL_RESULTS.md` and `reports/FINAL_RESULTS.json` (step 2).

Do NOT return `.env` or any file containing the API key. The packaging step
strips these automatically and the env report shows only whether a key was set.
