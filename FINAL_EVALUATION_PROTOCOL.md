# Final evaluation protocol (FROZEN)

Freeze version: `final-1.1`. Re-frozen on 2026-07-13 after judge-provenance,
homogeneity-gate, input-isolation, and single-answer-model hardening.
Machine-readable companions: `configs/release/final.yaml`, `FINAL_RUN_MATRIX.yaml`,
`FINAL_METRIC_DEFINITIONS.md`, `FINAL_ANALYSIS_PLAN.md`.
Hash manifest: `artifacts/manifests/freeze_hashes.json`.

This document freezes *how* the final evaluation is run and scored. It does not
introduce new results. Final numbers come only from
`artifacts/results_ledger.json` (final-candidate rows) and, once it lands, the
single homogeneous LongMemEval-M rerun defined here.

---

## 1. Scope

Two tracks, one frozen protocol.

### 1.1 MGP-6 v2 — final tables ALREADY LOCKED
All MGP-6 v2 headline numbers are final-candidate quality and are frozen in the
ledger (recomputed 2026-07-12 from 180-line prediction files by
`benchmarks/mgp6/metrics_mgp6.py`). The final tables are *regenerated*, not
re-run, from the ledger by `scripts/analysis/build_final_results.py`. The
remaining MGP-6 checks are local (no hosted model needed):

- **Few-shot (6-shot) decision baseline metric recompute — completed, run incomplete.**
  Coverage-aware rescoring over 180 gold items (174 predictions plus six
  aligned as INVALID) gives 0.7833 action accuracy and 0.7692 macro-F1. The
  frozen output is `runs_local/mgp6_few6_rescore/few6_report.json`. Because the
  original run has only 174/180 predictions, this is an `incomplete`
  coverage-aware bound, not a final-table result.
- **Verification rescore** of the locked rows (defensive; confirms the ledger
  values reproduce from the archived predictions).

### 1.2 LongMemEval-M — homogeneous rerun is the ONLY path to a final number
**No existing LongMemEval number is final.** The reported 77.2% (139/180) is a
selection-biased `failure_replay_only` construction: 110 retained v7 successes
(judge Gemma-4-31b-it, produced under a provider-contaminated run) + 25 machine
replay repairs (judge Qwen3.5-9B) + 4 Codex/GPT-5 overrides that the historical
artifact misleadingly labels `[human-adjudication]`. A non-empty Modal top-up
re-evaluated 84/110 carried-forward items: 71 remained correct and 13 regressed.
Together with the replay this is 96/154 raw observed, with a full-180 raw bound
of 53.3%-67.8%; this attempt cannot reproduce 77.2%. Rows therefore retain their
exact `diagnostic_only`, `failure_replay_only`, `incomplete`, `invalid`, or
`externally_pending` status until a homogeneous full-180 run completes.

The pending required run is a **homogeneous full-180 LongMemEval-M rerun** under
this frozen config: one configuration, one pass, all five systems, no
failure-replay patching, no manual adjudication baked into the numbers.

---

## 2. Systems matrix

| # | System | MGP-6 v2 | LongMemEval-M | Role |
|---|---|:--:|:--:|---|
| S1 | no-memory (b1) | yes | yes | reference floor |
| S2 | flat-vector retrieval (b2) | yes | yes | retrieval-only baseline |
| S3 | recency (b3) | yes | yes | recency-only baseline |
| S4 | naive-overwrite (b4) | yes | yes | destructive-update baseline |
| S5 | rule-KSA controller | yes | yes (controller) | contribution (rule policy) |
| S6 | LLM-KSA controller (qwen3.5-9b) | yes | (via controller path) | contribution (LLM-backed) |
| S7 | zero-shot LLM decision baseline | yes | - | decision-only ablation of the controller |
| S8 | few-shot (6-shot) LLM decision baseline | incomplete (coverage-aware rescore complete) | - | decision-only ablation |
| X | external adapters (Mem0, Letta/MemGPT, Graphiti, MemOS) | **MGP-6 only** | - | third-party comparison |

Rules:
- The homogeneous LongMemEval rerun evaluates exactly the five systems
  `controller, b4, b3, b2, b1` on the SAME 180 items in ONE configuration.
- **External adapters are MGP-6 only** and always carry a **mapping disclosure**:
  their native `NOOP` outcome has no KEEP/SUPERSEDE/ABSTAIN equivalent, so each
  external number is reported as the `NOOP->ABSTAIN` upper bound with the
  `NOOP->KEEP` lower bound stated alongside. MemOS is **bound-only**: its adapter
  cannot observe `replaced_old`, so supersession is inexpressible; it is never
  reported as a capability measurement (`diagnostic_only`).
- The two decision baselines (S7, S8) isolate "LLM makes the action call with no
  KSA scaffold" and are reported next to the LLM-KSA controller.

---

## 3. Judge policy

**Primary judge:** `google/gemma-4-31b-it:free` (OpenRouter).
**Fallback judge:** `google/gemma-4-31b-it` (non-free), fired **only on
operational failure** of the primary (HTTP error, empty content, or timeout
after the configured retries) — never for quality reasons and never as a silent
A/B. Temperature 0, JSON response format.

**Per-item judge logging (mandatory, one record per graded item in
`judgments.jsonl`):**

| Field | Meaning |
|---|---|
| `requested_judge` | the judge the protocol asked for (primary) |
| `judge_model_id` / `actual_judge` | the judge that actually returned the verdict |
| `used_fallback` | boolean; true iff the fallback graded this item |
| `fallback_reason` | why the primary failed (error class), empty if none |
| `attempts` | number of judge calls made for this item |
| `judge_rationale` / raw output | the judge's raw verdict text, retained verbatim |
| `prompt_hash` | sha256 of the exact judge prompt |

The **judge audit** (`scripts/evaluation/run_judge_audit.sh`) reads these fields
across all `judgments.jsonl` files and quantifies any primary/fallback confound
(accuracy split by `used_fallback`, fallback rate per competency), so a judge
switch can never be mistaken for a capability effect.

Known deviation to correct: the legacy deploy scripts
(`deploy/run_lme_v8_full_5systems.sh`) hardcode `JUDGE_MODEL=google/gemma-4-31b-it`
(the non-free route) with no fallback. The final wrapper
`scripts/evaluation/run_longmemeval_final.sh` overrides this to the
primary(:free) + fallback policy above and records both in the run manifest.

---

## 4. Seed policy

- Single global seed **0** for slice construction, bootstrap resampling, and any
  stochastic ordering. Model temperature is **0** throughout.
- The stratified slice is built once, deterministically
  (`scripts/build_stratified_slice.py`, `--seed 0`), giving
  `data/slices/longmemeval_m_strat30_seed0.jsonl` (6 competencies x 30 = 180),
  range `range_0_179`.
- All bootstrap CIs use seed 0 (see `FINAL_ANALYSIS_PLAN.md`).

---

## 5. Immutability rule

- Final runs write only under `runs_local/<run_id>/`.
- **A final run refuses to write into an existing non-empty final output dir.**
  Every wrapper checks the target dir before launching: if it exists and is
  non-empty and `--resume` was not passed, the wrapper exits with an error and
  changes nothing.
- `--resume` is the only way to continue an existing run dir; it resumes by shard
  union (per-shard resume + `src/ksa/eval/merge.py` dedup by `session_id`) and
  never rewrites already-scored items.
- Summaries are written atomically (`.tmp` then rename) so an interrupted write
  never leaves a half-file that a later resume would trust.
- Raw evidence archives (`../ksa_controller/`, `../mgp6_v2/`) and
  `artifacts/results_ledger.json` are **read-only inputs** and are never modified.

---

## 6. Adjudication policy

- **Both raw and adjudicated numbers are always reported.** "Raw" = the judge
  verdict as returned. "Adjudicated" = raw plus any documented human or model
  override, with the adjudicator kind stated accurately.
- Every override is logged **per item** with: `session_id`, competency, gold,
  prediction, machine verdict, override verdict, adjudicator identity, and
  rationale (the format of `adjudication_overrides.jsonl`).
- Adjudicator agreement (Cohen's kappa) is reported for any adjudicated set.
- For the homogeneous rerun the **primary claim is the raw number**; adjudication,
  if performed, is reported as a clearly separated sensitivity analysis and never
  substituted for the raw figure. The 77.2% selection-biased carry-forward
  construction is retained only to document its rejection, never as a result or
  headline.

---

## 7. Freeze declaration and hash manifest

The following inputs are frozen for `final-1.1`. Actual sha256 values live in
`artifacts/manifests/freeze_hashes.json` (computed 2026-07-13):

| Input | Purpose |
|---|---|
| `benchmarks/mgp6/data/mgp6_v2.jsonl` | MGP-6 v2 gold (180 items) |
| `prompts/` (combined hash) | extraction + relation prompt templates |
| `configs/models/openrouter_qwen_gemma.yaml` | model + judge routing spec |
| `configs/release/final.yaml` (self-hash) | this freeze's machine config |

Recompute the combined prompts hash exactly as:

```
sha256 over sorted(prompts/**/*) where each file contributes:
  relpath (posix) + b"\0" + file-bytes + b"\0"
```

The LongMemEval-M slice is not redistributed. Its external record in the freeze
manifest fixes the exact seed-0 180-item slice at SHA-256
`f10b4fb4173d3e2d9310d90c2b6bf8f5e7b147cea1d04affa9037b1b9fe6787d`
(180 unique rows); every run manifest recomputes that hash and
`scripts/verify_homogeneous_run.py` gates it.

Any edit to a frozen input, to `configs/release/final.yaml`, or to the systems /
judge / seed policy above **breaks the freeze** and requires a new freeze version
and a regenerated hash manifest.

---

## 8. What upgrades a claim from diagnostic to verified

Stated in full in `FINAL_ANALYSIS_PLAN.md` section "Decision rule". In brief: a
LongMemEval claim becomes citable only after the homogeneous rerun completes,
passes `scripts/verify_homogeneous_run.py` (one config, one judge policy, all 180
items, all five systems, no patching), and the pre-specified analysis is applied.
**Per-item inspection of the rerun before scoring is prohibited.**
