# Publication strategy

Updated: 2026-07-27.

## Paper identity

Submit this work as a diagnostic/evaluation and auditable-systems paper, not a
leaderboard or method-superiority paper. The defensible identity is:

1. write transition, resulting state/lineage, retrieval, and downstream answer
   are separate evaluation layers;
2. a deployed typed five-dimensional write rule is exactly replayable and its
   effective mechanism can be measured by dimension, memory type, and guard;
3. MGP-6 v4.3 is a controlled three-way semantic diagnostic with a one-shot
   sealed result and explicit shortcut gates;
4. the homogeneous LongMemEval V12 run supplies downstream evidence and full
   pipeline accounting; and
5. negative and ineligible evidence remains visible rather than being blended
   into headline results.

The scorecard, v2 lexical policy, and v4.3 composed controller are distinct
implementations. Never attribute one experiment's predictions to another.

## Eligible primary evidence

- MGP-6 v4.3 sealed hidden, single pre-registered composed controller:
  0.8481 accuracy / 0.8479 macro-F1 with component-cluster intervals.
- Hidden operational error decomposition: 30 state-preserving
  ABSTAIN→KEEP lapses and 8 state-corrupting ABSTAIN→SUPERSEDE errors.
- LongMemEval V12 homogeneous 180-item slice: controller 137/180 (76.1%) versus
  naive overwrite 114/180 (63.3%), paired Holm-corrected `p=2.9e-4`.
- V12 scorecard replay: both stored scores and all 12,654 actions reproduce
  exactly from `(c,e,f,r,rho)`.
- V12 mechanism probes: leave-one-dimension-out changes
  8 / 0 / 779 / 483 / 0 actions for `c/e/f/r/rho`; removing the relation guard
  changes 11,091 KEEP decisions to SUPERSEDE.
- V12 type analysis: the observed action profiles differ by type, while a
  common stability prior changes zero decisions and common thresholds change
  five.
- V12 pipeline accounting: extraction plus relation classification consume
  92.8% of prompt tokens and 99.4% of model calls.

## Eligible development and diagnostic evidence

- V4.3 public-development baselines, ablations, external adapters, component
  decomposition, cost matrices, and successor configuration. Every presentation
  must retain the development-only qualification.
- V2 conflict-type-only and type-only shortcut results as construct-validity
  failures.
- V2 no-lineage ablation as a measurement demonstration: action accuracy is
  unchanged while lineage integrity collapses.
- Contaminated v7, selected replay, and top-up bounds only as reasons those
  artifacts are ineligible.
- The single-session-preference taxonomy as descriptive analysis with an
  unexecuted intervention.

## Forbidden readings

- No hidden comparison for v4.3 baselines, ablations, external systems,
  components, or successors.
- No claim that exact scorecard replay establishes write correctness,
  optimality, calibration, or causal value; V12 has no candidate-level gold
  write actions.
- No claim that all five dimensions were active on V12. Marker burden, signed
  relation, and the relation guard carry almost all observed variation.
- No capability claim from v2, contaminated v7, or the 77.2% carry-forward
  construction.
- No population, deployment-safety, state-of-the-art, non-inferiority,
  multi-human-independence, or monetary-cost claim.
- No priority claim for write operations, abstention, typed memory, provenance,
  lineage, operation-level evaluation, or “memory governance.”

## Submission gate

Before submission:

1. regenerate the scorecard, v4.3, and LongMemEval tables from raw artifacts;
2. pass the bibliography audit and compile the anonymous PDF without overfull
   content, undefined references, or missing citations;
3. preserve the one-shot hidden/development distinction everywhere;
4. verify every abstract number against `claims_evidence_matrix.md`;
5. keep v2, v4.3, and V12 annotation/evidence regimes separate;
6. check current venue policy and related work against primary sources; and
7. resolve redistribution licensing before publishing non-public data.

## One-paper decision

Keep one paper. The scorecard mechanism audit, controlled v4.3 diagnostic, and
V12 downstream result are complementary layers of the same contribution. The
single-session-preference intervention remains unexecuted and does not justify
a separate empirical claim.
