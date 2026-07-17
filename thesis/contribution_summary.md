# Defensible Contribution Summary

## One-sentence claim

This thesis contributes a layered evaluation and construct-validity audit for
KEEP/SUPERSEDE/ABSTAIN memory writes over typed, provenance-tracked,
lineage-preserving state.

## What is contributed

1. An explicit three-action write and state-transition interface.
2. Separate action, state/lineage, and answer-level measurement.
3. Released per-item predictions and shortcut, cluster-bootstrap, calibration,
   risk–coverage, and asymmetric-cost analysis.
4. A measured negative result: conflict type alone perfectly predicts the MGP-6
   v2 test labels, so the current pilot is not independent validation.
5. A prospective role-separated v3 protocol with long trajectories, hidden
   labels, native external metrics, and three-human annotation.

## Strongest findings

- Conflict-type-only lookup: 1.000 held-out accuracy; type-only: 0.9667.
- Reference policy: 0.8889 / 0.9145 on test; structured LLM: 0.9000 / 0.9040.
- Reference-minus-LLM family-cluster interval includes zero.
- Reference: 0/33 observed action false commits, upper bound 0.0868, and 10/45
  missed updates; cost regimes reverse the preferred policy.
- No-lineage ablation: unchanged action accuracy but lineage integrity
  0.8556→0.3689, as a within-generator measurement demonstration.

## Explicit non-claims

The thesis does not claim controller superiority, matching, non-inferiority,
population safety, calibrated confidence, multi-human agreement, native-system
rankings from mapped adapters, a final LongMemEval score, or generalization to
long-lived deployment. It does not claim priority for updating, abstention,
typing, provenance, lineage, governance, or operation-level evaluation.

## Open evidence

Independent v3 generation, three-human annotation, component-oracle runs,
multiple models/seeds, native external comparisons, and a complete homogeneous
downstream run remain unexecuted and are never imputed.
