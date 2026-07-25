# Final analysis plan (FROZEN; V12 reused-slice analyses are exploratory)

Freeze version: `final-2.0` (2026-07-18). The V12 implementation was selected
after inspecting the partial V11 outcomes on this same LongMemEval-M slice.
Therefore its tests, intervals, and acceptance readout are descriptive and
exploratory on this slice; a new untouched holdout is required for a genuinely
pre-specified confirmatory claim.

Implementation anchors: `benchmarks/mgp6/metrics_mgp6.py` (`paired_mcnemar`,
`BootstrapReporter`), `scripts/analysis/mcnemar_mgp6.py` (MGP-6 family, stdlib,
read-only), `scripts/evaluation/evaluate_single_session_preferences.py` (SSP
bootstrap), `src/ask/eval/longmemeval.py` (`build_eval_report` bootstrap CIs).

---

## 1. Confidence intervals — stratified bootstrap

- **Resamples:** 10,000. **Seed:** 0. **Method:** stratified percentile bootstrap
  (2.5% / 97.5% percentiles).
- **Strata:**
  - MGP-6: `(type, gold_action)` — the strata already used by
    `metrics_mgp6.BootstrapReporter` (resample within each stratum, with
    replacement, preserving stratum sizes).
  - LongMemEval: `competency` (6 strata x 30). SSP-only selections are a single
    stratum (ordinary item bootstrap).
- **Reported for:** every headline accuracy (overall + per-competency + per-action),
  false-commit rate, lineage integrity, stale-retrieval rate, SSP accuracy, and
  every SSP rate (F2/F3).
- Note: the shipped MGP-6 scorer defaults to 1,000 bootstrap iterations for speed;
  the **final** CIs are recomputed at 10,000 (`--bootstrap 10000`) with seed 0.

## 2. Paired system comparisons — exact McNemar

- For two systems evaluated on the **same items**, build the 2x2 discordance table
  (a_only_correct, b_only_correct) and compute the **exact two-sided McNemar
  p-value** (exact binomial on the discordant cells, p=0.5), identical to
  `metrics_mgp6.paired_mcnemar` (lines 567-583).
- MGP-6: paired on the same **180** scenarios by `scenario_id`.
- LongMemEval: paired on the same **180** questions by `session_id`, using the
  homogeneous rerun's `judgments.jsonl` for both systems (same judge policy).
- Discordant-cell count of 0 -> p = 1.0 by definition.

## 3. Paired bootstrap for accuracy differences

- For each pre-specified pair, resample **paired** items (10,000 reps, seed 0) and
  report the distribution of the accuracy **difference** (system A - system B) with
  a 95% percentile CI. Pairing preserves the item-level correlation McNemar uses.
- This complements McNemar: McNemar gives the significance of the discordance;
  the paired bootstrap gives the CI on the magnitude of the accuracy gap.

## 4. Pre-specified comparison family + Holm correction

The confirmatory family is **exactly** the following comparisons. Holm-Bonferroni
correction is applied **within each track's family** (MGP-6 family; LongMemEval
family; SSP family) to the McNemar p-values, sorted ascending, threshold
`alpha / (m - i + 1)` at rank `i` of `m`, alpha = 0.05.

### 4a. MGP-6 family (m = 4; on the locked 180-item predictions)
1. rule-ASK controller **vs** b4 (naive-overwrite)
2. rule-ASK controller **vs** b2 (flat-retrieval)
3. LLM-ASK controller (qwen3.5-9b) **vs** zero-shot decision baseline
4. rule-ASK controller **vs** LLM-ASK controller (qwen3.5-9b)
   (`scripts/analysis/mcnemar_mgp6.py` computes comparisons 1-4; comparison 3 here
   is that script's "llm_controller vs zero_shot"; it also reports controller-vs-
   llm_controller.)

### 4b. LongMemEval family (m = 2; on the homogeneous rerun, same 180 questions)
1. controller **vs** b4 (naive-overwrite)
2. controller **vs** b2 (flat-vector)

### 4c. SSP ablation family (m = 6; on the 30 SSP items, paired vs baseline arm A)
Full method (arm F) **vs each** of arms A (baseline), B, C, D, E, G — i.e. the
five contrasts F-vs-{A,B,C,D,E} plus F-vs-G, per
`docs/research/SINGLE_SESSION_PREFERENCE_METHOD.md`. (Runs only after the PROPOSED
correction code is implemented; see the run matrix statuses.)

Any comparison NOT in this list is exploratory and is reported as such, never as a
confirmatory result.

## 5. Effect sizes

- **Risk difference (primary):** `acc(A) - acc(B)` with the paired-bootstrap 95% CI
  (section 3). Also report the Newcombe (Wilson-based) CI for the risk difference
  as a distribution-light cross-check (implemented in `scripts/analysis/mcnemar_mgp6.py`).
- **McNemar odds ratio:** `b_only / a_only` (discordant cell ratio).
- **Per-system marginal accuracy** with a Wilson score 95% CI.
- For SSP rates (unsupported-preference, cross-person contamination): risk
  difference vs baseline with paired-bootstrap CI.

## 6. Decision rule — diagnostic -> verified

A claim is **upgraded from diagnostic to verified** only when ALL hold:

1. The homogeneous LongMemEval-M rerun `lme_final_5systems_v12_qwen_180` completes and
   passes `scripts/verify_homogeneous_run.py` (one config, one judge policy across
   all items, all 180 items present per system, all five systems, no failure-replay
   patching, no adjudication baked into the raw number).
2. The judge audit (`run_judge_audit.sh`) confirms zero model-fallback rows and
   separately reports any deterministic scoring-fallback rows.
3. The pre-specified analysis (sections 1-5) is applied and reported raw first,
   adjudicated second.

The controller release has an additional pre-specified acceptance target:
`scripts/analysis/check_controller_accuracy_gate.py` must verify at least
153/180 correct (85%). A controller-only run can satisfy this engineering target,
but it does not replace the five-system run required for comparative claims.

Specific upgrades that the rerun enables:
- **"Controller LongMemEval accuracy = X% (CI ...)"** becomes available for the
  first time iff (1)-(3) hold. The v7 61.1% remains diagnostic and the 77.2%
  selection-biased construction remains `failure_replay_only`; neither is a
  prior final result to replace.
- **"Controller vs b4 on LongMemEval"** may be claimed in the direction the rerun
  shows, with McNemar + paired-bootstrap, iff Holm-corrected significance holds.
  Until then the honest statement stands: under the contaminated v7 config b4
  (63.3%) leads the controller (61.1%), so controller superiority on LongMemEval is
  **unsupported**.
- **Few-shot MGP-6 decision baseline** remains incomplete after the coverage-aware
  rescore because only 174/180 predictions exist. The 0.7833/0.7692 values may be
  disclosed only as coverage-aware incomplete-run estimates; a citable row
  requires a complete pre-specified rerun.
- **SSP correction claims** require the ablation matrix, which requires the PROPOSED
  correction code to be implemented and run; until then no SSP-improvement claim is
  made. The v7 11/30 value is only a contaminated diagnostic reference; the
  incomplete top-up observed 8/29 correct with one unresolved (maximum 9/30).

MGP-6 final-candidate rows are already locked and need no upgrade; the MGP-6 family
tests (4a) are confirmatory analyses on the locked predictions, not new runs.

## 7. Blinding / integrity guard (mandatory)

- **Per-item inspection of the rerun's outputs before scoring is prohibited.** The
  rerun is scored by the frozen pipeline end-to-end; analysts do not read
  individual `answers.jsonl` / `judgments.jsonl` rows, tune any threshold, or
  choose any comparison after seeing per-item outcomes. Only the aggregate reports
  and the pre-specified tests in this plan are examined.
- No metric, threshold, prompt, seed, judge, or comparison may be changed after the
  rerun starts. Any such change breaks the freeze (new freeze version + new hash
  manifest, disclosed).
- Adjudication, if performed at all, happens only after the raw number is recorded,
  is fully logged per item, and is reported as a separate sensitivity analysis.
