# Claims → Evidence Matrix

Date: 2026-07-13. Every claim that could plausibly appear in the abstract of a
paper or thesis, with its strength tag, the evidence path(s) that back it, and the
**exact phrasing allowed at venue**. Strength tags:
`verified` (recomputed/tested here) · `supported` (in evidence, with caveat) ·
`suggestive` (indicative, confounded) · `hypothesized` (proposed, not run) ·
`future_work` (requires a run that does not exist).

Reproduction anchors: statistics in `reports/STATISTICAL_ANALYSIS.md` and
`reports/statistical_analysis_raw_output.txt`; canonical numbers in
`artifacts/results_ledger.json`; final tables in `reports/FINAL_RESULTS.{md,json}`.

---

## A. MGP-6 governance claims

| # | Claim | Tag | Evidence path(s) | Allowed venue phrasing |
|---|---|---|---|---|
| A1 | Ablating abstention collapses decision safety: invalid-commit 0.0 → 1.0, accuracy 0.9222 → 0.5556. | verified | `artifacts/results_ledger.json` (ablation/no_abstain); `artifacts/mgp6_v2/ablations/no_abstain/report.json` | "On the MGP-6 diagnostic slice (n=180), removing the abstention component raises the invalid-commit rate from 0.0 to 1.0 and drops action accuracy from 0.92 to 0.56." |
| A2 | Ablating provenance yields invalid-commit 0.606, accuracy 0.700. | verified | ledger (ablation/no_provenance); `.../ablations/no_provenance/report.json` | "Removing provenance raises invalid-commit to 0.61 (accuracy 0.70)." |
| A3 | Ablating typing zeroes KEEP F1 (accuracy 0.7889). | verified | ledger (ablation/no_typing); `.../ablations/no_typing/report.json` | "Removing typing drives KEEP F1 to 0." |
| A4 | Ablating lineage leaves action accuracy unchanged but drops lineage integrity 0.8556 → 0.3689. | verified | ledger (ablation/no_lineage); `.../ablations/no_lineage/report.json` | "Lineage affects supersession-chain integrity (0.86→0.37), not the action label." |
| A5 | The rule controller makes only conservative errors (14 SUPERSEDE→ABSTAIN; invalid-commit 0.0). | verified | ledger (controller_rule confusion); `artifacts/mgp6_v2/ref_5systems/controller/{report.json,predictions.jsonl}` | "The controller never invalidly commits; its 14 residual errors are all conservative SUPERSEDE→ABSTAIN misses." |
| A6 | Rule controller = 0.9222/0.9399 full corpus; 0.8889/0.9145 test split. | verified | ledger; `.../ref_5systems/controller/report.json` | "0.89 action accuracy on the held-out test split (0.92 full corpus)." Always give the test-split figure first. |
| A7 | The governance formulation significantly beats an unstructured zero-shot decision baseline: LLM controller 0.8889 vs zero-shot 0.700 (RD +0.189, McNemar exact p 8.2e-06, Holm p 1.6e-05, OR 3.83). | verified | `reports/STATISTICAL_ANALYSIS.md` §1.2 Pair 4; `reports/statistical_analysis_raw_output.txt` | "Casting the decision as structured governance improves an LLM decision baseline by 18.9 points on MGP-6 (McNemar p<1e-4, Holm-corrected)." |
| A8 | The rule and LLM controllers are statistically indistinguishable on MGP-6 action accuracy (RD +0.033, Holm p 0.286, 95% CI includes 0). | verified | STATISTICAL_ANALYSIS §1.2 Pair 3 | "We find no significant action-accuracy difference between the rule and LLM controllers (Holm p=0.29)." Must NOT be phrased as rule superiority. |
| A9 | Rule controller >> B2 (flat-retrieval) and B4 (naive-overwrite): RD +0.79 / +0.50, exact p 3.6e-43 / 1.6e-27, one-directional (c=0). | supported | STATISTICAL_ANALYSIS §1.2 Pairs 1–2 | "The controller outperforms flat-retrieval and naive-overwrite baselines by large margins; because the rule policy is aligned with the labels, this comparison is diagnostic, not a general-capability result." |
| A10 | The rule controller has premise resistance 1.0 vs the LLM controller's 0.0889. | supported | ledger (per-run premise_resistance); reports | "The rule controller resists false premises (1.0) where the 9B LLM controller does not (0.09)." Descriptive metric, not hypothesis-tested. |
| A11 | External memory systems on MGP-6 upper-bound (NOOP→ABSTAIN) at Letta 0.678, Mem0 0.622, Graphiti 0.383; MemOS 0.144 is a structural bound. | suggestive | ledger (external/*); `artifacts/mgp6_v2/ext_*/controller/report_noop_abstain.json` | "Under a favourable NOOP→ABSTAIN mapping, off-the-shelf systems upper-bound at 0.68/0.62/0.38; MemOS cannot express supersession through its adapter." Always show the mapping. |

## B. Annotation / dataset claims

| # | Claim | Tag | Evidence path(s) | Allowed venue phrasing |
|---|---|---|---|---|
| B1 | One independent human annotator agrees with gold: raw 0.9889 [0.9667,1.0], Cohen κ 0.98146 [0.93997,1.0], 1 disagreement. | supported | ledger (annotation_human_independent); `benchmarks/mgp6/annotations/human/human_annotation_agreement_summary.json` | "One independent annotator reached κ=0.98 with the gold labels (n=90, one disagreement)." |
| B2 | A 4-LLM panel agrees: Fleiss κ 0.9815, majority vote 100% vs gold. | supported | ledger (annotation_panel_4llm); `mgp6_v2/annotation/*.csv` | "A four-model audit panel reached Fleiss κ=0.98 (majority vote 100% vs gold)." Never call this human IAA. |
| B3 | MGP-6 v2 is a 180-item, 6-type, author-designed diagnostic slice (60/30/90). | verified | ledger (mgp6_v2.dataset); `mgp6_v2/data/mgp6_v2.jsonl` | "MGP-6 v2, an author-designed 180-item diagnostic slice (six conflict types)." |

## C. LongMemEval claims

| # | Claim | Tag | Evidence path(s) | Allowed venue phrasing |
|---|---|---|---|---|
| C1 | In contaminated v7, single-session-preference is the weakest competency: 11/30 (0.3667), CI [0.20, 0.53]; the selected replay repairs 0/19 failures, while the top-up reaches at most 9/30. | supported diagnostic | ledger; SSP taxonomy; Modal top-up shards | "SSP is the weakest v7 competency (11/30); none of its 19 selected failures is repaired by replay, and the incomplete top-up reaches at most 9/30." Do not call it unchanged across versions. |
| C2 | SSP failures are dominated by grounding-supply (retrieval-omission + contamination): primary 10/19, present 15/19. | supported | SSP taxonomy JSON (`primary_category_counts`, `pipeline_layer_counts`) | "SSP failures are primarily grounding-supply failures (present in 15/19), with the decisive turn out-ranked by distractors." |
| C3 | The historical 77.2% (139/180) LongMemEval construction. | failure_replay_only (not a result) | ledger; failure-replay artifact; Modal top-up | "A selection-biased carry-forward construction of 77.2% that is contradicted by the non-empty top-up (96/154 raw observed; full-180 bound 53.3%-67.8%)." It may appear only to explain invalid evidence. |
| C4 | The v7 controller is diagnostic-only (110/180, 61.1%), provider-contaminated (316 HTTP-402, 388 empty fallbacks). | supported | ledger (v7/controller); `docs/audit/CONTROLLERRUN_FAILURE_LEDGER.md` F1 | "The v7 run is diagnostic-only owing to provider contamination." |
| C5 | On the contaminated v7 slice, naive-overwrite (63.3%) outperforms the controller (61.1%). | supported | ledger (v7 b4 vs controller); source-of-truth §1 | "Under the contaminated v7 configuration the controller did not beat naive overwrite; no comparative LongMemEval claim is currently supported." |
| C6 | The governance controller improves long-horizon end-task accuracy over baselines. | future_work |, (no clean run exists) | Do not claim. Requires the frozen homogeneous full-180 rerun (`FINAL_EVALUATION_PROTOCOL.md`). |

## D. Framing / method claims

| # | Claim | Tag | Evidence path(s) | Allowed venue phrasing |
|---|---|---|---|---|
| D1 | ASK is an interpretable, abstention-aware, typed+provenance memory-governance formulation. | verified (as a design) | `src/ask/`; `README.md` | "We formulate memory governance as explicit KEEP/SUPERSEDE/ABSTAIN over typed, provenance-tracked memories." |
| D2 | A typed preference record + provenance-constrained retrieval + answer contract would repair most SSP failures. | hypothesized | SSP analysis §7; `SINGLE_SESSION_PREFERENCE_METHOD.md` (proposed) | "We propose (and do not yet evaluate) provenance-constrained preference grounding as the highest-leverage fix." |
| D3 | The approach is "safe" for long-lived agents. | suggestive (scope-limited) | ledger (invalid-commit 0.0 on MGP-6) | Restrict to: "the controller never invalidly commits on the MGP-6 diagnostic (invalid-commit 0.0)." Do not generalise to end tasks. |
| D4 | Results are fully reproducible. | supported (partial) | `reports/REPRODUCIBILITY_CHECKLIST.md`; `Makefile`; `.github/workflows/ci.yml` | "Code, MGP-6 data, per-item predictions, seeds, and CIs are released; LongMemEval data is external; several runs are pending." |

---

## Phrasing rules (must-follow)

1. Never write "MGP-6 benchmark", always "author-designed diagnostic slice".
2. Never write "multi-annotator / human inter-annotator agreement", "one
   independent annotator plus a four-model audit panel".
3. Never write "the rule controller outperforms the LLM controller", the
   difference is non-significant (Holm p 0.29).
4. The 77.2% appears only as a selection-biased `failure_replay_only` construction with judge
   composition and the pending-rerun caveat; never as an abstract headline.
5. External-adapter numbers always carry the NOOP mapping and "upper bound";
   MemOS is a structural bound, not a capability.
6. Lead MGP-6 with the test-split figure (0.89), full corpus (0.92) secondary.
7. Any cross-task / cross-model generalisation is `future_work` until the frozen
   homogeneous rerun and full-benchmark evaluation exist.
