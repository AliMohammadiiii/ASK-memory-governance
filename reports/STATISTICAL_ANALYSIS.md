# Statistical Analysis

Date: 2026-07-15. Author role: skeptical statistician / adversarial reviewer.
The primary MGP-6 analysis is `scripts/analysis/audit_mgp6_validity.py` and its
machine-readable output. Historical item-level analyses below are retained as
secondary provenance. Every number is either (a) read from the released
artifacts or (b) computed by `scripts/analysis/mcnemar_mgp6.py`
(raw output preserved verbatim in `reports/statistical_analysis_raw_output.txt`).
No value was invented or loosely re-estimated.

---

## 0. Executive summary of statistical status

| Track | Statistical evidence that EXISTS | Statistical evidence that is PENDING |
|---|---|---|
| **MGP-6 v2** | Held-out shortcut probes; 10,000-replicate template-family and minimal-pair cluster bootstrap; family-macro estimates; finite-sample safety bounds; calibration, risk–coverage, and cost sensitivity; complete per-item predictions; one-human plus four-model label audit; coverage-aware few6 rescore | Role-separated v3 construction; independent three-human IAA; hidden confirmation runs; a complete pre-specified few6 run |
| **LongMemEval-M** | Contaminated v7 diagnostics, selection-biased failure replay, and incomplete top-up bounds. No clean comparative test or inferential CI for a complete v8 run. | Homogeneous full-180 final-1.1 rerun. It is `externally_pending` after the supplied credential returned HTTP 403. Until it passes the frozen gate, **no comparative superiority claim is statistically supported.** |

The single most consequential finding is the construct-validity failure:
`conflict_type` alone reaches 1.000 held-out accuracy and macro-F1. The policy
comparison is secondary: on test, reference minus structured-LLM accuracy is
−0.0111 with a paired template-family interval [−0.0938, 0.0625]. The LLM is
numerically higher, and the data support neither superiority nor non-inferiority.

---

## 1. MGP-6 v2 — historical item-level paired tests (secondary, n = 180)

These full-corpus tests include training and development items, assume item-level
independence that the template analysis rejects, and operate on a dataset whose
shortcut gate fails. They are preserved for reproducibility, not as the primary
inferential basis of the paper or thesis.

### 1.1 Method (exactly as computed)

- **Unit of analysis:** the 180 MGP-6 v2 scenarios (full corpus: 60 train / 30 dev
  / 90 test). Items are paired across systems by `scenario_id`.
- **Correctness rule (replicated from `mgp6_v2/metrics_mgp6.py`):** `predicted_action`
  is canonicalised to `{KEEP, SUPERSEDE, ABSTAIN, INVALID_COMMIT, INVALID}`
  (anything else → `INVALID`, per `load_predictions` lines 69–74); an item is
  correct iff `predicted_action == gold_action` (`action_accuracy` line 112).
  Gold actions are only KEEP/SUPERSEDE/ABSTAIN, so `INVALID_COMMIT`/`INVALID`
  predictions are always incorrect.
- **Test:** exact two-sided McNemar on the discordant cells (identical formula to
  the repo's own `paired_mcnemar`, exact binomial with p = 0.5).
- **Multiplicity:** Holm–Bonferroni across the 4-test pre-specified family, α = 0.05.
- **Effect sizes:** paired risk difference (RD = acc_A − acc_B) and McNemar odds
  ratio b/c. RD confidence intervals by Newcombe method 10 (Wilson-based, paired)
  and by an item-level paired bootstrap (10 000 reps, seed 20260712). Marginal
  accuracies carry Wilson score 95% CIs.

Per-system marginal accuracy (canonicalised, full corpus) — matches the ledger exactly:

| System | Correct / n | Accuracy | Wilson 95% CI |
|---|---|---|---|
| rule_controller | 166 / 180 | 0.9222 | [0.8737, 0.9531] |
| llm_controller_qwen35_9b | 160 / 180 | 0.8889 | [0.8346, 0.9269] |
| zero_shot_decision | 126 / 180 | 0.7000 | [0.6294, 0.7622] |
| b4_naive_overwrite | 76 / 180 | 0.4222 | [0.3524, 0.4953] |
| b2_flat_retrieval | 24 / 180 | 0.1333 | [0.0913, 0.1907] |

### 1.2 Results table

| # | Pair (A vs B) | acc A | acc B | b (A✓B✗) | c (A✗B✓) | discordant | RD (A−B) | RD Newcombe 95% | RD bootstrap 95% | OR (b/c) | McNemar exact p | Holm p | Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | rule_controller vs b4_naive_overwrite | 0.9222 | 0.4222 | 90 | 0 | 90 | +0.5000 | [+0.4230, +0.5690] | [+0.4278, +0.5722] | ∞ (c=0) | 1.616e-27 | 4.847e-27 | **reject H0** |
| 2 | rule_controller vs b2_flat_retrieval | 0.9222 | 0.1333 | 142 | 0 | 142 | +0.7889 | [+0.7181, +0.8382] | [+0.7278, +0.8444] | ∞ (c=0) | 3.587e-43 | 1.435e-42 | **reject H0** |
| 3 | rule_controller vs llm_controller_qwen35_9b | 0.9222 | 0.8889 | 14 | 8 | 22 | +0.0333 | [−0.0188, +0.0873] | [−0.0167, +0.0833] | 1.750 | 2.863e-01 | 2.863e-01 | **retain H0** |
| 4 | llm_controller_qwen35_9b vs zero_shot_decision | 0.8889 | 0.7000 | 46 | 12 | 58 | +0.1889 | [+0.1096, +0.2664] | [+0.1111, +0.2667] | 3.833 | 8.220e-06 | 1.644e-05 | **reject H0** |

Full 2×2 concordance tables (e = both correct, b = A-only, c = B-only, d = both wrong):

- Pair 1: e=76, b=90, c=0, d=14
- Pair 2: e=24, b=142, c=0, d=14
- Pair 3: e=152, b=14, c=8, d=6
- Pair 4: e=114, b=46, c=12, d=8

### 1.3 Interpretation (skeptical)

1. **Reference policy vs weak baselines is design-aligned, not capability evidence.**
   In both comparisons the discordance is one-directional (c = 0): there is **not a
   single item** where B2 or B4 is uniquely correct. The odds ratio is therefore
   infinite and the exact p-values are astronomically small (1.6e-27, 3.6e-43).
   This is the expected consequence of a design in which the rule controller
   encodes the labelling policy and B2/B4 cannot express supersession/abstention —
   it is expected and **partly tautological** (see Reviewer-2 audit, "baseline fairness").
2. **Rule controller vs LLM controller: NOT significant (Holm p = 0.286).** The
   raw gap is only 3.3 pp (14 vs 8 discordant items), the RD 95% CIs straddle 0
   ([−0.019, +0.087] Newcombe; [−0.017, +0.083] bootstrap). **A paper must not
   claim the rule controller beats a capable LLM controller on overall action
   accuracy.** The defensible controller-vs-LLM claim is *qualitative* and lives
   elsewhere: premise-resistance 1.0 vs 0.0889 and invalid-commit 0.0 vs 0.0758
   (different, non-accuracy metrics — reported descriptively, not tested here).
3. **LLM controller vs zero-shot decision is descriptive despite the small item-level p-value.**
   The historical full-corpus gap is large, but prompt structure and policy
   scaffolding are evaluated on a shortcut-leaking author-designed collection.
   It is not a clean estimate that the framework helps on an independent task.
4. **Scope limit.** All four tests are *within-corpus* on an author-designed slice.
   Statistical significance here bounds sampling error only; it says nothing about
   external generalisation, template dependence, or construct validity. See
   `THREATS_TO_VALIDITY.md`.

### 1.4 Additional MGP-6 statistics available (from the ledger, not re-tested here)

- Full-corpus reference-policy confusion is one-directional conservative: KEEP 24/24, ABSTAIN
  66/66, SUPERSEDE 76/90 with the 14 misses all going SUPERSEDE→ABSTAIN
  (invalid-commit rate 0.0). On held-out test the action false-commit count is
  0/33, but its one-sided 95% upper bound is 0.0868; this is not a safety guarantee.
- Test-split-only figures (n=90): rule controller 0.8889 / macro-F1 0.9145
  (vs full-corpus 0.9222 / 0.9399) — report both, never full-corpus alone.
- Annotation agreement is inferential evidence about the *labels*, not the systems:
  1 human annotator over 90 test items, raw agreement 0.9889 [0.9667, 1.0], Cohen's
  κ 0.98146 [0.93997, 1.0], 1 disagreement (`MGP6V2-T3-TEST-016`); plus a 4-LLM
  panel, Fleiss κ 0.9815, majority vote 100% vs gold. This is **n=1 human +
  model-panel audit, not multi-human IAA.**

---

## 2. LongMemEval-M — diagnostic only, no new comparative claims

**Per the source of truth and the leakage audit, no LongMemEval number is final and
no comparative superiority claim is statistically supported.** I therefore compute
**no** new hypothesis test on LongMemEval. Only the CIs already recorded in the
ledger are restated, each with its `claim_eligibility` label.

| Run | n | correct | accuracy | CI (as recorded) | claim_eligibility |
|---|---|---|---|---|---|
| v8 failure-replay construction (after overrides) | 180 | 139 | 0.7722 | historical bootstrap, not inferentially valid for a complete v8 run | failure_replay_only |
| v8 failure-replay construction (raw) | 180 | 135 | 0.7500 | — | failure_replay_only |
| v7 controller (post-adjudication) | 180 | 110 | 0.6111 | — | diagnostic_only |
| v7 controller (pre-adjudication) | 180 | 108 | 0.6000 | — | diagnostic_only |
| v8 nothink replay (70 selected v7 failures) | 70 | 25 | 0.3571 | — | failure_replay_only |
| v8 Modal top-up | 84 observed of 110 | 71 | 0.8452 observed-only | combined raw 96/154; full-180 bound [0.533, 0.678] | incomplete |
| single-session-preference (v7) | 30 | 11 | 0.3667 | [0.20, 0.5333] bootstrap (n=20000, seed 0) | diagnostic_only |
| single-session-preference (top-up attempt) | 29 observed of 30 | 8 | — | maximum 9/30 | incomplete |

Statistical reasons these cannot support a comparative claim (from the audit docs):

1. **No confirmation set.** The v7→v8 fixes were designed on the exact 70 v7
   failures and the v8 replay was run on that same set; there is no untouched
   LongMemEval set. The 77.2% is a selection-biased carry-forward construction,
   not a rerun.
2. **Judge heterogeneity confounded with item difficulty.** The 139/180 mixes
   Gemma-4-31b (110 retained-correct), Qwen3.5-9B (66 replay), and GPT-5 (4
   overrides); judge identity is confounded with difficulty because the replayed
   items are exactly the prior failures.
3. **The carry-forward assumption is empirically contradicted.** The Modal top-up
   re-executed 84/110 retained-success items and found 13 regressions. Combined
   with replay, only 96/154 are raw-correct; even assigning all 26 unresolved
   items correct gives 122/180 = 67.8%, below 77.2%.
4. **Residual provider contamination.** The selection-biased construction still
   carries v7's HTTP-402/empty-extraction history into 110 slots.
5. **The direction can invert.** Under the contaminated v7 config, the naive-overwrite
   baseline B4 (114/180 = 63.3%) *outperformed* the v7 controller (110/180 = 61.1%).
   Any "controller wins on LongMemEval" claim is currently **unsupported**.

The usable LongMemEval evidence is limited to **diagnostic failure-mode findings**.
In v7, SSP is 11/30 (CI [0.20, 0.53]) and the selected replay repairs 0/19 v7
failures, but the replay also changes prompt contexts and cannot isolate the
answer model. The top-up contradicts the claimed carry-forward: SSP is 8/29
observed with one unresolved (maximum 9/30). See `ERROR_TAXONOMY.md`.

---

## 3. Reproduction

```bash
python3 scripts/analysis/mcnemar_mgp6.py            # prints table + JSON
python3 scripts/analysis/mcnemar_mgp6.py --mgp6-root /path/to/mgp6_v2
```

- Script: `scripts/analysis/mcnemar_mgp6.py` (stdlib only; READ-ONLY on run artifacts).
- Raw output: `reports/statistical_analysis_raw_output.txt`.
- Inputs (read-only): `mgp6_v2/data/mgp6_v2.jsonl` (gold) and the five
  `predictions.jsonl` files under `artifacts/mgp6_v2/{ref_5systems/controller,
  ref_5systems/b4, ref_5systems/b2, llm_qwen35_9b/controller,
  llm_decision_zero/controller}`.
- Determinism: exact McNemar and Newcombe are closed-form; the bootstrap uses a
  fixed seed (20260712) and 10 000 reps.
