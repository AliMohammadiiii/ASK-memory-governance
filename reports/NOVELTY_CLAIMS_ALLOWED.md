# Novelty claims allowed

Updated 2026-07-27 after the MGP-6 v4.3 and LongMemEval V12 audits.

Rules of use: each claim is allowed only at the stated evidence level and with
the corresponding boundary. The project makes no “first” or “to our knowledge”
claim. Recent work contains close precedents for write operations, conflict
handling, lineage, typing, abstention, and operation-level evaluation.

## A. Core conjunction

**A1. Allowed.** “We operationalize a three-way write policy-KEEP, lineage-
preserving SUPERSEDE, or write-time ABSTAIN-over typed, provenance-tracked
records and evaluate the write decision separately from stored state/lineage,
retrieval, and downstream answers.”

- Required precedents: Memory-R1 for discrete write operations; Zep/Graphiti
  and TOKI for retained history and write-time conflict control; MemGuard and
  MemOS for typing; HaluMem for operation-level evaluation; selective
  prediction and RSCB-MC for abstention/feature control.
- Boundary: the controlled conjunction and separable measurement are the
  contribution; none of the ingredients is claimed as an invention.

**A2. Allowed.** “The evaluation harness makes action correctness, state
invariants, lineage integrity, superseded-record recoverability, stale
retrieval, selective risk, and asymmetric write costs separately observable.”

- Boundary: claim implemented instrumentation, not novelty for each metric.

## B. Five-dimensional controller

**B1. Allowed.** “The deployed LongMemEval V12 writer evaluates each candidate
on extraction confidence, evidence quality, marker burden, signed
candidate–prior relation, and a memory-type stability prior, then applies
type-conditional thresholds and a discrete relation-update guard.”

- Boundary: the weights and thresholds are hand-specified, not learned,
  calibrated, or optimal.

**B2. Allowed.** “The published rule exactly replays both stored scores and all
12,654 V12 actions from the action log.”

- Boundary: this is execution fidelity, not candidate-level write correctness.

**B3. Allowed.** “On V12, marker burden determines the observed abstentions,
signed relation determines supersessions, and removing the relation guard would
convert 11,091 KEEP decisions to SUPERSEDE.”

- Required qualification: a deterministic counterfactual on the fixed log, not
  a retrained-system or population causal estimate.

**B4. Allowed.** “Memory types have different observed action profiles, but the
stability prior changes no action and common thresholds change only five.”

- Required qualification: descriptive evidence; the hand-set durability
  ordering is implemented but weakly exercised.

## C. MGP-6 v4.3 diagnostic

**C1. Allowed.** “MGP-6 v4.3 is a controlled 900-item diagnostic with 100
nine-item semantic components, all three write actions inside each component,
component-isolated splits, and executable duplicate and shortcut gates.”

- Boundary: synthetic, author-designed, single-slot, single-step, and not a
  community or population benchmark.

**C2. Allowed.** “The single pre-registered composed controller reaches 0.8481
accuracy / 0.8479 macro-F1 on the sealed hidden split.”

- Required qualification: no hidden baseline, ablation, component, external,
  successor, or paired comparison exists.

**C3. Allowed.** “On hidden, 30 of 38 gold-ABSTAIN errors preserve state through
KEEP, while 8 replace a record on insufficient evidence.”

- Boundary: operational error decomposition on synthetic data, not a safety
  certification.

**C4. Allowed.** “On public development, neither the model component nor the
public-evidence rule component alone reaches the composed accuracy; the guard
repairs 37 model errors and introduces 9.”

- Required qualification: development-only component analysis.

## D. Downstream evidence and implementation

**D1. Allowed.** “On one homogeneous 180-item LongMemEval-M slice, governed
writes reach 76.1% versus 63.3% for naive overwrite under the frozen answer
model and judge.”

- Required qualification: one slice, answer model, judge, and seed; no broad
  capability or deployment claim.

**D2. Allowed.** “Write-time ingestion consumes 92.8% of V12 prompt tokens and
99.4% of model calls; extraction is the dominant stage.”

- Boundary: measured provider trace accounting, not hardware FLOPs or monetary
  cost.

**D3. Allowed.** “The deterministic date/numeric/list helper is separately
auditable and cannot explain the aggregate gain: it bypassed the answer model
zero times and its two controller substitutions produced one repair and one
regression.”

- Boundary: answer-layer implementation result, not a write-controller gain.

**D4. Allowed.** “Structured action logs, raw extraction/relation traces,
atomic lineage transitions, active-only retrieval, content-addressed caches,
immutable manifests, and resumable stages make the pipeline auditable.”

- Boundary: implementation/reproducibility contribution, not a learning claim.

## E. Negative and exclusion claims

**E1. Allowed.** “MGP-6 v2 fails its construct-validity check because conflict
type alone predicts every held-out action.”

- Boundary: v2 motivates v4.3; it supports no general evidence-reasoning claim.

**E2. Allowed.** “The v2 no-lineage ablation leaves action accuracy unchanged
while lineage integrity falls from 0.8556 to 0.3689.”

- Boundary: within-generator measurement demonstration, not external method
  validation.

**E3. Allowed.** “The contaminated v7 and 77.2% carry-forward construction are
ineligible; the homogeneous V12 run supersedes them.”

- Boundary: do not average, compare, or promote those artifacts into a primary
  result.

## F. Claims not allowed

- “ASK invents memory write actions, abstention, typed memory, provenance,
  lineage, operation-level evaluation, or memory governance.”
- “The five-feature scorecard achieves high gold write accuracy on V12.”
- “All five scorecard dimensions materially contribute on V12.”
- “V4.3 baselines or successors were beaten on the sealed hidden split.”
- “The hidden result demonstrates deployment safety or real-world
  generalization.”
- “V2 demonstrates general evidence reasoning.”
- “The project has independent multi-human validation for v4.3.”
- “The reported token/latency traces establish monetary cost or hardware
  efficiency.”
