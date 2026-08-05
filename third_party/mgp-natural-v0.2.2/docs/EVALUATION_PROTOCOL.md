# Evaluation Protocol

## Reporting boundary

Every result is reported separately for StudyChat and WikiConv. No mixed headline accuracy or macro-F1 is permitted. Combined training may be evaluated, but each test track retains its own result table and interpretation.

## Primary metrics

For each track, the primary classification metric is macro-F1 over `KEEP`, `SUPERSEDE`, and `ABSTAIN`. Report accuracy, per-class precision, recall, F1 and support, and the complete confusion matrix. Macro-F1 is primary because natural action prevalence may be imbalanced.

## Structured metrics

When corresponding predictions exist, report:

- evidence-set precision, recall, and F1;
- resulting-state exact match;
- canonicalized resulting-state match;
- lineage edge F1;
- joint action-plus-state exact match;
- prediction and exclusion-aware coverage;
- calibration error and Brier score;
- confidence-stratified accuracy;
- selective risk; and
- abstention precision and recall.

`SUPERSEDE` resulting-state metrics are conditional on gold `SUPERSEDE` items and must include support. Evidence scoring uses turn-ID sets; an ordered-span diagnostic may be added without replacing set metrics.

## Statistical uncertainty

Confidence intervals use a deterministic, pinned bootstrap. StudyChat resamples user or continuity components, and WikiConv resamples continuity components. Item-level IID bootstrap may appear only as a labeled sensitivity analysis. Paired system comparisons use identical items and clusters. Multiple-comparison control is required when many systems or slices are tested, and effect sizes accompany significance tests.

## Evaluation views

The protocol defines:

1. prevalence-preserving full view;
2. balanced diagnostic action view;
3. StudyChat task-state view;
4. StudyChat preference view;
5. StudyChat cross-session view;
6. WikiConv editorial-state view;
7. short-context view;
8. long-distance-evidence view;
9. ambiguity-heavy view; and
10. trajectory view.

View membership is generated from adjudicated metadata under a frozen rule. Balanced diagnostics are not the primary benchmark prevalence.

## Frozen transfer protocols

- train StudyChat, test StudyChat;
- train WikiConv, test WikiConv;
- train StudyChat, zero-shot test WikiConv;
- train WikiConv, zero-shot test StudyChat;
- combined training, separately test each track;
- leave-scope-out;
- leave-user-group-out; and
- leave-editorial-component-out.

Domain-transfer failures are interpreted against source naturalness, discourse roles, state principal, revision evidence, and prevalence differences.

## Baselines

Frozen interfaces are provided for no-memory, recency, overwrite, flat retrieval, deterministic rule, zero-shot language model, structured MGP controller, oracle-evidence, and oracle-action state-reconstruction diagnostics. External model execution requires explicit authorization. Paid APIs and silent fallback are disabled by default.

Each run manifest records model identifier, provider, revision, prompt hash, code hash, seed, temperature, tools, timestamp, retry and fallback policies, input manifest hash, output hash, cost if any, and failure counts.

## Hidden-test discipline

Hidden-test model performance may not be inspected while constructing candidates, changing guidelines, selecting models, or tuning thresholds. Any unsealing is logged and requires authorization. Provisional constructor-label smoke scoring is accepted only with `--allow-provisional-smoke`; its report must say `publication_eligible = false` and may not enter the paper results.

## Robustness

Frozen robustness protocols cover paraphrase, context truncation, distractors, conflicting evidence, order perturbation, anonymization perturbation, long-context distance, domain shift, slot-name variation, candidate ambiguity, calibration, and guideline sensitivity. Perturbations are classified as label-preserving or decision-changing before evaluation. Hidden-test perturbations are not tuning data.

