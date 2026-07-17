# Data leakage and researcher degrees of freedom

Audit date: 2026-07-13. This document records choices that could inflate, selectively improve, or complicate interpretation of the reported results. It distinguishes an observed run from a construction assembled after observing failures.

## 1. Failure-derived LongMemEval changes

The v8 changes were designed after inspecting the exact 70 v7 controller failures. The completed v8 replay then evaluated those same 70 failures. This is direct adaptive reuse of the evaluation set: the replay is failure_replay_only, not confirmation evidence.

The replay prompt contexts also differ from the v7 contexts. Therefore persistence or repair across v7 and replay cannot isolate the answer model as the cause; it reflects a changed pipeline and judging regime.

Mitigation: only a frozen, homogeneous full-slice rerun can be used as a comparative LongMemEval result. That final-1.1 run is externally_pending.

## 2. Selection-biased carry-forward construction

The historical 77.2% figure is not an observed homogeneous v8 run. It was assembled by:

- carrying forward all 110 v7 controller successes;
- replacing only the 70 v7 failures with a replay in which 25 were machine-judged correct; and
- adding four post-hoc Codex/GPT-5 semantic overrides, producing 139/180 instead of the raw 135/180.

This construction conditions the new method on having failed before while assuming every old success remains a success. That asymmetry mechanically prevents regressions from entering the headline.

The non-empty Modal top-up demonstrates that the assumption is false for this attempt. It completed 84 of the 110 former-success items: 71 remained correct and 13 regressed. Combining those observations with the completed 70-item replay gives 96 correct among 154 observed items. Even if every one of the 26 unresolved items were correct, the full-180 raw accuracy would lie between 53.3% and 67.8%. If the four replay adjudication overrides are added, the corresponding bounds are 55.6% to 70.0%. Thus this v8 attempt cannot reproduce 77.2%.

Required classification: the 75.0% raw construction and 77.2% adjudicated construction are failure_replay_only. The top-up is incomplete. None is a final LongMemEval performance estimate.

## 3. Single-session preference selection artifact

The 11/30 single-session-preference value in the failure-replay merge is a carry-forward artifact, not an unchanged v8 measurement:

- 19 prior failures were replayed and 0/19 were repaired;
- 10 of 11 former successes were completed in the top-up and only 8 remained correct; and
- one former success is unresolved.

The observed attempt is therefore 8/29, with a maximum possible value of 9/30 (30.0%), not 11/30. The failure mode is still diagnostically important, but the prior 36.7% value must not be represented as a clean v8 result.

## 4. Adjudication and judge heterogeneity

The v7 controller result changed from 108/180 to 110/180 through two manual adjudications applied to the retained evidence. The constructed replay result changed from 135/180 to 139/180 through four Codex/GPT-5 overrides. Those four records are machine-assisted adjudications and must not be described as independent human adjudication.

The constructed result also mixes evidence selected by outcome across judging regimes: Gemma judgments for the 110 retained v7 successes, Qwen judgments for the 70 replayed failures, and four Codex/GPT-5 overrides. Judge identity is therefore confounded with item difficulty and selection. Raw and adjudicated values must remain separate, and neither may be promoted beyond failure_replay_only.

## 5. Provider and execution contamination in v7

The v7 controller artifact contains 316 HTTP-402 traces, 388 empty extraction fallbacks, at least 12 manual relaunches, and 736 extraction errors in total. Its escalation tier was a no-op because the configured big and fast models were the same. The v7 controller result, 110/180 post-adjudication, and all same-run baseline comparisons are diagnostic_only.

The v7 naive-overwrite baseline scored 114/180 while the controller scored 110/180. No claim of LongMemEval superiority is supported by this evidence.

## 6. Author-designed MGP-6 diagnostic

MGP-6 scenarios, gold labels, labeling policy, prompts, and rule controller were produced in the same research effort. High rule-controller performance can therefore reflect policy/template alignment. MGP-6 must be described as an author-designed synthetic diagnostic, not an established independent benchmark or representative population sample.

Mitigations:

- report the held-out 90-item test split alongside the 180-item full-corpus score;
- retain the LLM-backed controller and zero-shot baseline as same-dataset comparisons;
- disclose one independent annotator over the test split, with human identity resting on author attestation; and
- describe the four-model panel as a model audit, never as human inter-annotator agreement.

Residual risk: one independent annotator does not establish multi-annotator human reliability, and the author-created manual may make agreement easier by construction.

## 7. MGP-6 split and denominator freedom

The dataset contains 60 train, 30 development, and 90 test examples. Full-corpus scores include train and development items and must be labeled full-180; they are not test-only estimates.

The six-shot baseline produced 174 predictions because its six exemplars were not evaluated. Its recomputed artifact aligns all 180 gold IDs and treats the six missing IDs as INVALID, giving coverage-aware accuracy 0.7833 and macro-F1 0.7692. This is a useful bound, but the underlying run remains incomplete and is not directly comparable to completed 180-prediction runs.

## 8. External-adapter mapping freedom

External adapters expose actions that do not map one-to-one onto KEEP, SUPERSEDE, and ABSTAIN. Both NOOP-to-KEEP and NOOP-to-ABSTAIN mappings must be reported whenever an external result is used. Selecting only the better mapping would be researcher freedom disguised as a single score.

MemOS cannot expose supersession through the evaluated adapter. Its 0.144 result is diagnostic_only: it is a structural harness bound, not a measurement of the system's full capability.

## 9. Metric revision and uninformative metrics

The invalid-commit definition was revised late; backup source files document the prior semantics. Only reports generated with the current scorer may be combined. The shipped over-forgetting and under-forgetting metrics saturate at 1.0 for every system and are not informative enough for claims.

## 10. Prompt and template overlap

MGP-6 scenario templates and controller prompts were authored together. Template-family identifiers permit a family-level holdout analysis, but that analysis has not been run. Until it is, generalization beyond these template families remains untested.

## 11. Slice selection

The LongMemEval-M evaluation slice is the deterministic seed-0 selection of 30 items from each of six competencies. The supplied 180-row slice matches recomputation from the 500-row source, and no re-sampling evidence was found. This reduces slice-selection freedom but does not remove adaptation to failures within the slice.

## 12. External execution blocker

The frozen final-1.1 protocol was smoke-tested without persisting credentials. A minimal Qwen request and provider-specific probes returned HTTP 403 before inference. No final predictions were generated. This is an execution blocker, not evidence about model quality; final-1.1 remains externally_pending.

## Integrity decision

The 2026-07-15 shortcut audit supersedes the older `final_candidate` interpretation for MGP-6 v2: conflict type alone reaches 1.000 held-out accuracy, so all current policy, ablation, and mapped-adapter scores are diagnostic observations on an author-designed generator, not capability estimates. LongMemEval supports only diagnostic failure analysis, incomplete bounds, and a documented account of why the 77.2% construction is not a valid result. Stronger claims require both the role-separated MGP-6 v3 confirmation and the externally pending homogeneous LongMemEval run to pass their frozen gates.
