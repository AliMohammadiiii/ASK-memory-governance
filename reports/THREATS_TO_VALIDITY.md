# Threats to Validity

Date: 2026-07-15. Structured against the four classical validity types. Every
instance cites a concrete artifact; every threat carries a mitigation status of
**mitigated**, **partially mitigated**, or **open**. Sources:
`docs/audit/DATA_LEAKAGE_AND_RESEARCHER_DEGREES_OF_FREEDOM.md`,
`docs/audit/SCIENTIFIC_SOURCE_OF_TRUTH.md`,
`docs/audit/CONTROLLERRUN_FAILURE_LEDGER.md`,
`docs/audit/INVALID_AND_SUPERSEDED_RUNS.md`, and the ledger.

---

## 1. Internal validity — does the design support the causal story?

| # | Threat | Concrete instance | Status |
|---|---|---|---|
| I1 | **Dataset/controller circularity and label leakage.** Scenarios, gold labels, and the released lexical reference policy were authored in one effort. | Conflict type alone reaches 1.000 held-out accuracy; type alone reaches 0.9667. | **confirmed threat**: current policy scores are diagnostic. Cluster bootstrap cannot repair the construct failure; role-separated v3 data are required. |
| I2 | **Failure-derived fixes without a confirmation set (LongMemEval).** v7→v8 fixes were designed on the exact 70 v7 failures and replayed on that set. | 77.2% is `failure_replay_only`; top-up contradicts its carry-forward assumption. | **open**: frozen homogeneous full-180 rerun required; currently externally pending after HTTP 403. |
| I3 | **Model-assisted override contamination and mislabelling.** Overrides were applied after machine verdicts. | v7: 5 in-place overrides (108→110/180). Replay merge: 4 Codex/GPT-5 overrides (135→139/180), historically tagged `[human-adjudication]`, κ 0.880. | **partially mitigated**: raw/construction values separated and labels corrected; these overrides are not final evidence. |
| I4 | **Residual provider contamination carried forward.** 110 v7-retained-correct sessions never re-executed under the fixed pipeline. | Failure ledger F1/F2/F9 residual note; 316 HTTP-402, 388 empty fallbacks in v7. | **open**: only a clean prepaid rerun retires this. |
| I5 | **Split hygiene (MGP-6).** The reference policy was developed against train/dev; full-corpus numbers include those items. | Splits 60/30/90; test reference 0.8889/0.9145 versus structured LLM 0.9000/0.9040. | **partially mitigated for reporting**: test is primary, but the type/action mapping persists across splits, so split hygiene does not establish validity. |
| I6 | **Metric revision mid-project.** `invalid_commit` semantics revised late. | `.bak_invalid_commit_outcome` files preserved; leakage audit §7. | **mitigated**: all current reports use the revised definition; pre-revision numbers quarantined. |

---

## 2. External validity — does it generalise beyond this setup?

| # | Threat | Concrete instance | Status |
|---|---|---|---|
| E1 | **MGP-6 is an author-designed diagnostic slice, not a community benchmark.** | 180 items, 6 synthetic scenario types, 96 template families; README + source-of-truth §1. | **open and confirmed**: positioned only as diagnostic; mapped external adapters do not provide independent validation. Role-separated v3 or third-party data are required. |
| E2 | **LongMemEval evaluated on a 180-item slice, not the full 500.** | Stratified 30×6 seed-0 slice; ledger `longmemeval_m.dataset`. | **open**: full-benchmark evaluation pending. |
| E3 | **Single base model / single seed.** Qwen3.5-9B answerer; one seed for LME runs. | SSP CIs reflect item sampling, not run-to-run variance (SSP analysis §8). | **open**: multi-seed / multi-model runs pending. |
| E4 | **External-adapter numbers are harness-and-mapping specific.** | NOOP→ABSTAIN vs NOOP→KEEP mappings; MemOS cannot express supersession. Leakage audit §6. | **partially mitigated**: both mappings retained; MemOS flagged bound-only. |
| E5 | **Synthetic-template dependence.** Templates, visible conflict/type metadata, labels, and the reference policy share an authoring process. | Shortcut audit: conflict/type lookup generalises across the released split. | **confirmed threat**: a family holdout over v2 alone is insufficient because the label mapping persists; v3 must place all actions inside each family and pass pre-unblinding shortcut gates. |

---

## 3. Construct validity — are we measuring what we claim?

| # | Threat | Concrete instance | Status |
|---|---|---|---|
| C1 | **"Human IAA" would be a mis-description.** Annotation is n=1 human + a separate 4-LLM panel. | Human κ 0.98146 [0.93997,1.0], 1 disagreement; panel Fleiss κ 0.9815. | **partially mitigated by wording**. **Open**: three blinded human annotators plus independent adjudication on v3. |
| C2 | **Panel may share the author's reading** because the labelling manual is unambiguous by construction. | Leakage audit §4 residual risk. | **open**. |
| C3 | **Forgetting metrics uninformative.** `over_forgetting_rate`/`under_forgetting_rate` saturate at 1.0 for every system. | Ledger `known_metric_issues`. | **mitigated by disclosure**: excluded from claims. |
| C4 | **Judge as construct proxy (LongMemEval).** Correctness = LLM-judge verdict, with known number-word/date false negatives. | Failure ledger F6; residual numeric-guard hard-rejects. | **partially mitigated**: guard fixes + deferral to judge; residual manual adjudication. |
| C5 | **Premise resistance / invalid-commit are bespoke metrics**, not externally validated constructs. | Rule 1.0 vs LLM 0.0889 premise resistance on the full pilot; action false commit is separately defined as committing on gold-ABSTAIN. | **partially mitigated**: definitions separated and reported descriptively; action error, resulting state, and downstream answer must not be conflated. |

---

## 4. Statistical-conclusion validity — are the inferences sound?

| # | Threat | Concrete instance | Status |
|---|---|---|---|
| S1 | **Small and clustered samples.** MGP-6 test n=90 across 48 template families; SSP n=30. | `artifacts/analysis/mgp6_validity_audit.json`. | **partially mitigated**: template-family and minimal-pair cluster bootstrap, family-macro estimates, exact counts, and finite-sample bounds; external uncertainty remains open. |
| S2 | **Multiplicity across the pre-specified family.** 4 paired MGP-6 tests. | Holm–Bonferroni applied; the one null (rule vs LLM) survives correction as non-significant. | **mitigated**: Holm correction reported. |
| S3 | **Over-claiming from a tautological comparison.** rule vs B2/B4 give c=0, OR=∞. | McNemar p ~1e-27 / 1e-43 but design-driven. | **mitigated by framing**: reported as "not sampling noise", not as capability proof. |
| S4 | **The reference-vs-LLM null is easy to misreport as equality or non-inferiority.** Held-out RD −0.0111; paired family interval [−0.0938, 0.0625]. | Validity audit paired cluster result. | **mitigated for wording**: LLM is numerically higher; no superiority, equivalence, matching, or non-inferiority claim. |
| S5 | **Selection and judge heterogeneity invalidate inference from the 77.2% CI.** Three judges are confounded with item difficulty, and 110 items are carried forward. | The historical CI [0.711, 0.833] is not an inferential interval for a complete v8 run; the top-up bounds the observed attempt at 53.3%-67.8%. | **open**: single-policy homogeneous rerun pending. |
| S6 | **Direction can invert on LongMemEval.** Under contaminated v7, B4 (63.3%) > controller (61.1%). | Source-of-truth §1. | **open**: no supported comparative LME claim until rerun. |

---

## 5. Priority actions (in decreasing order of validity impact)

1. **Execute the role-separated MGP-6 v3 protocol** — independent writers, all actions inside every family, long trajectories, sealed labels, and shortcut rejection gates.
2. **Recruit three blinded human annotators plus independent adjudication** for v3.
3. **Evaluate oracle and predicted components with native external-system operations** and family-clustered, cost-sensitive analysis.
4. **Execute the frozen homogeneous full-180 LongMemEval rerun** only after input, provider, judge, and provenance gates pass.
5. **Complete a pre-specified few-shot run.** Coverage-aware rescoring is complete,
   but the archived run still has only 174/180 predictions and remains incomplete.
