# Final metric definitions (FROZEN)

Freeze version: `final-1.1` (2026-07-13). Every metric that appears in a final
table is defined here with its formula, numerator/denominator, directionality
(higher-is-better `up` / lower-is-better `down`), edge cases, and the exact code
that implements it. Two MGP-6 metrics are explicitly **excluded** from final
tables (section "Excluded metrics").

Implementation anchors:
- MGP-6 scorer: `benchmarks/mgp6/metrics_mgp6.py`
- MGP-6 schema / gold access: `benchmarks/mgp6/mgp6_schema_v2.py`
- LongMemEval scorer: `src/ksa/eval/longmemeval.py` (`build_eval_report`, `LongMemEvalGrader`)
- SSP evaluator: `scripts/evaluation/evaluate_single_session_preferences.py`
- Paired significance: `benchmarks/mgp6/metrics_mgp6.py` (`paired_mcnemar`) and
  `scripts/analysis/mcnemar_mgp6.py`

Notation: an *item* is one scenario (MGP-6) or one question (LongMemEval).
`gold` = gold label/action; `pred` = predicted label/action. Action canonicalisation
(`KEPT->KEEP`, `NOOP->ABSTAIN`, unknown->`INVALID`, etc.) is applied to both sides
by `canonical_action()` before any comparison.

---

## A. Action-decision metrics (MGP-6)

### A1. Action accuracy
- **Formula:** mean over items of `1[canonical(gold_action) == canonical(pred_action)]`.
- **Numerator / denominator:** items with matching action / all items.
- **Direction:** up.
- **Edge cases:** a missing prediction aligns as `INVALID` and counts wrong
  (`align()` fills missing with `predicted_action="INVALID"`). Gold actions are
  only KEEP/SUPERSEDE/ABSTAIN, so `INVALID`/`INVALID_COMMIT` predictions are
  always incorrect.
- **Code:** `metrics_mgp6.action_accuracy` (line 133).

### A2. Macro-F1
- **Formula:** unweighted mean of per-action F1 over `{KEEP, SUPERSEDE, ABSTAIN}`.
- **Direction:** up.
- **Edge cases:** if precision+recall == 0 for an action, its F1 is defined as 0.
- **Code:** `metric_report` macro_f1 = `mean(action_f1(sample, a) for a in ACTIONS)`
  (line 459); `action_f1` (line 153).

### A3. Per-action precision / recall / F1  (KEEP, SUPERSEDE, ABSTAIN)
- **Precision (label L):** `TP_L / (predicted == L)` = fraction of items predicted
  L whose gold is L.
- **Recall (label L):** `TP_L / (gold == L)` = fraction of gold-L items predicted L.
- **F1 (label L):** harmonic mean of the two.
- **Direction:** up.
- **Edge cases:** empty denominator -> 0 via `safe_mean`.
- **Code:** `action_precision` (137), `action_recall` (145), `action_f1` (153);
  surfaced under `per_action` (492).

### A4. False-commit rate (a.k.a. invalid-commit rate, gold-ABSTAIN scope)
- **Definition:** on gold-ABSTAIN items, the system *committed* when it should
  have abstained.
- **Formula:** over items with `gold_action == ABSTAIN`, mean of
  `1[ pred_action != ABSTAIN  OR  (active predicted state - allowed gold state) is non-empty ]`.
- **Numerator / denominator:** gold-ABSTAIN items that committed / all gold-ABSTAIN items.
- **Direction:** down (0.0 is best; the rule controller is 0.0).
- **Edge cases:** committing extra active memory even while nominally "ABSTAIN"
  still counts as a false commit (state-level check, not just the label).
- **Code:** `metrics_mgp6.invalid_commit` (315), exported as both
  `invalid_commit_rate` and `abstention_invalid_commit_rate` (470-471).

### A5. Invalid-commit outcome rate (prediction-level, full slice)
- **Definition:** fraction of ALL items whose predicted outcome is the explicit
  `INVALID_COMMIT` token (used mainly for black-box external adapters).
- **Formula:** mean over all items of `1[pred_action == INVALID_COMMIT]`.
- **Direction:** down.
- **Code:** `invalid_commit_outcome` (332), exported as `invalid_commit_outcome_rate`.

### A6. Unnecessary-abstention rate
- **Definition:** on items whose gold requires a commit (`gold in {KEEP, SUPERSEDE}`),
  the fraction the system abstained on.
- **Formula:** `#(gold in {KEEP,SUPERSEDE} AND pred == ABSTAIN) / #(gold in {KEEP,SUPERSEDE})`.
- **Numerator / denominator:** wrongly-abstained commit items / all commit items.
- **Direction:** down.
- **Code:** derived from the confusion matrix (`metric_report.confusion_matrix`,
  500-517): sum the `ABSTAIN` column over gold rows `KEEP` and `SUPERSEDE`, divide
  by their gold counts. (For the rule controller this is the 14 SUPERSEDE->ABSTAIN
  conservative failures / 90 = 0.156 on SUPERSEDE, 0 on KEEP.)

---

## B. Selective-prediction metrics (MGP-6; require per-item confidence)

### B1. Coverage
- **Definition:** fraction of items on which the system elects to answer (does not
  defer), at a given confidence threshold / operating point.
- **Formula:** `#answered / #total`. In the risk-coverage curve, coverage is swept
  in 10 steps (0.1..1.0) over items sorted by descending confidence.
- **Direction:** context-dependent (reported jointly with selective accuracy).
- **Code:** `risk_coverage` (546): `count = ceil(n * coverage)` items retained.

### B2. Selective accuracy
- **Definition:** action accuracy computed only on the covered (answered) subset.
- **Formula:** `action_accuracy` over the top-`coverage` items by confidence.
- **Direction:** up.
- **Code:** `risk_coverage` per-step `action_accuracy` (546-563).

### B3. Risk-coverage
- **Definition:** the (coverage, risk) curve, `risk = 1 - selective_accuracy`.
- **Formula:** for each coverage c in {0.1..1.0}: `risk(c) = 1 - selective_acc(c)`,
  with a bootstrap CI per point.
- **Direction:** the curve should stay low (low risk) as coverage grows.
- **Edge cases:** returns `None` if any item lacks a confidence value (the curve is
  only computed when every prediction carries `confidence in [0,1]`).
- **Code:** `risk_coverage` (546).

---

## C. Memory-state / lineage metrics (MGP-6)

### C1. Artifact (memory-state) correctness — exact
- **Definition:** predicted memory state equals gold memory state field-for-field
  after normalisation and id-sort.
- **Formula:** mean over items of `1[ normalized_state(pred) == normalized_state(gold) ]`.
- **Direction:** up.
- **Edge cases:** compares the fixed field set
  `(id, type, text, confidence, status, supersedes_id, valid_from, semantic_slot, source)`;
  non-dict records are dropped.
- **Code:** `artifact_exact` (207), `normalized_state` (183).

### C2. Artifact (memory-state) correctness — semantic
- **Definition:** the set of *active* records matches on
  `(semantic_slot, type, canonicalised text)`, ignoring ids/order/inactive rows.
- **Formula:** mean of `1[ active_signature(pred) == active_signature(gold) ]`.
- **Direction:** up.
- **Code:** `artifact_semantic` (216), `active_signature` (168).

### C3. Lineage integrity (lineage correctness)
- **Definition:** on SUPERSEDE items, a 5-point check that the supersession was
  recorded as a proper lineage edge, not a destructive overwrite.
- **Formula:** over gold-SUPERSEDE items, mean of the 5-point row score:
  (1) old record marked `superseded`; (2) new record `active` with correct text;
  (3) new record's `supersedes_id` points at the old id; (4) old text no longer
  active in the same slot; (5) exactly one active record of the new type in the slot.
- **Numerator / denominator:** summed points / (5 x #SUPERSEDE items).
- **Direction:** up. (Rule controller 0.8556; `no_lineage` ablation drops it to 0.3689
  while leaving action accuracy unchanged — this metric is what isolates lineage.)
- **Code:** `lineage_correctness` (293), `lineage_row` (268).

### C4. Stale-retrieval rate
- **Definition:** the system's answer surfaces a value the scenario explicitly
  forbids (a superseded/stale value leaking into the answer).
- **Formula:** over items that declare `forbidden_answer_patterns`, fraction whose
  `predicted_answer` matches any forbidden pattern.
- **Numerator / denominator:** items leaking a forbidden value / items with any
  forbidden pattern.
- **Direction:** down.
- **Code:** `stale_retrieval` (257).

---

## D. Answer-quality / cue metrics (MGP-6, supporting)

These support the analysis but are not headline table columns. Included for
completeness because the ledger and reports reference them.

- **Premise-resistance rate** — on `query_mode == premise_resistance` items, the
  answer must include all required spans, exclude all forbidden spans, AND contain
  an explicit rejection token. Direction up. `premise_resistance` (378).
- **Implicit-application accuracy** — on `query_mode == implicit_application`
  items, the answer satisfies both include and exclude constraints. Up.
  `implicit_application` (388).
- **Judge include / exclude / conjunction rate** — deterministic
  pattern-based answer check (`judge_flags`, 364; `judge_rate`, 370).
- **Implicit-conflict recall / explicit-cue supersede recall / cue-dependence
  gap** — SUPERSEDE recall split by cue type (396-413).

---

## E. LongMemEval-M metrics

### E1. QA accuracy (overall)
- **Definition:** fraction of the 180 questions the judge marks correct.
- **Formula:** `#correct / #questions`, `correct` from `LongMemEvalGrader.grade()`.
- **Numerator / denominator:** judge-correct questions / all judged questions.
- **Direction:** up.
- **Edge cases:** blank/degenerate/refusal/abstention guards run before the LLM
  judge; the hard gold-token reject fires only on a provable numeric conflict
  (all other mismatches defer to the semantic judge). Every verdict logs the
  judge that produced it (`judge_model_id`, `used_fallback`).
- **Code:** `src/ksa/eval/longmemeval.py` `build_eval_report` (904) over
  `GradeResult`s; grading in `LongMemEvalGrader.grade` (646).

### E2. Per-competency accuracy
- **Definition:** E1 restricted to each of the 6 competencies (30 items each):
  knowledge-update, multi-session, single-session-assistant,
  single-session-preference, single-session-user, temporal-reasoning.
- **Formula:** `#correct_in_competency / #items_in_competency` (= /30).
- **Direction:** up.
- **Code:** `build_eval_report` per-competency decomposition.

### E3. Raw vs adjudicated accuracy
- **Definition:** E1 computed on raw judge verdicts (headline) and, separately, on
  the adjudicated set (raw + logged overrides). Both are always reported; the raw
  number is the primary claim for the homogeneous rerun.
- **Direction:** up.
- **Adjudicator agreement:** Cohen's kappa over machine-vs-adjudicator verdicts.

---

## F. Single-session-preference (SSP) metrics

The contaminated v7 diagnostic reference is **11/30**. It is not a verified
cross-version baseline: the incomplete Modal top-up observes 8/29 correct with
one unresolved (maximum 9/30). The correction method
(`docs/research/SINGLE_SESSION_PREFERENCE_METHOD.md`) is PROPOSED; the metrics
below are the frozen definitions for when the ablation matrix is run. SSP items
are the LongMemEval competency whose label contains `preference`.

### F1. SSP (preference) accuracy
- **Definition:** E1 restricted to the 30 SSP items.
- **Formula:** `#correct_SSP / 30`, with a stratified percentile bootstrap 95% CI.
- **Direction:** up.
- **Code:** `scripts/evaluation/evaluate_single_session_preferences.py`
  (`stratified_bootstrap_accuracy_ci`, n=20000, seed 0).

### F2. Unsupported-preference rate
- **Definition:** fraction of asserted preference tuples
  `(holder, target, attribute, polarity)` in the answer that do NOT trace to a
  retrieved `source_evidence` span.
- **Formula:** `#ungrounded_asserted_tuples / #asserted_tuples`.
- **Numerator / denominator:** answer-asserted tuples with no retrieved provenance
  / all answer-asserted tuples.
- **Direction:** down. Scores the "assert-only-grounded" answer contract.
- **Code:** PROPOSED (method doc section 5); not yet implemented — flagged pending.

### F3. Cross-person contamination rate
- **Definition:** fraction of answers whose asserted preference binds to an
  entity/persona from a non-supporting (distractor) session rather than the
  evaluated user.
- **Formula:** `#answers_bound_to_distractor_persona / #SSP_answers`.
- **Direction:** down. (The `75832dbd` / `75f70248` failure mode.)
- **Code:** PROPOSED (method doc section 5); not yet implemented — flagged pending.

### F4. Per-subtype breakdown
- Accuracy plus F2/F3 broken out by the taxonomy's primary categories
  (retrieval-omission, cross-session-contamination, target-attribute-extraction-miss,
  distractor-entity-binding, polarity-error, immediate-vs-enduring,
  unsupported-answer-specificity), so each ablation arm's credit is attributed to
  the mechanism it targets. PROPOSED (method doc section 5).

---

## Excluded metrics (never in final tables)

- **`over_forgetting_rate`** and **`under_forgetting_rate`** — these **saturate at
  1.0 for every system** in the shipped implementation and are therefore
  uninformative. They are computed (`over_forgetting` line 225, `under_forgetting`
  line 239) and remain in `report.json` for provenance, but MUST NOT appear in any
  final table or claim. (Ledger `known_metric_issues`.)

## Known issues carried with any MGP-6 table

- The `invalid_commit` metric was recently revised; `.bak` files of the prior
  definition are preserved. Final tables use the current
  `metrics_mgp6.invalid_commit` (gold-ABSTAIN commit violation).
- MGP-6 v2 is an author-designed diagnostic slice with **one** independent human
  annotator (Cohen's kappa ~0.98) plus a four-model audit panel — never described
  as multi-annotator human IAA.
