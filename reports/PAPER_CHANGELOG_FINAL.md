# Final Paper Changelog

Date: 2026-08-06

## Scientific identity

- Changed the title to **ASK: Auditable Governance of Long-Term Memory in
  Language Agents**.
- Rebuilt the abstract, introduction, contribution list, method, discussion,
  and conclusion around ASK as the contribution.
- Moved MGP-6 after the ASK formulation, protocol, architecture, and evaluation
  methodology.
- Recast MGP-6 v4.3 as a controlled decision diagnostic rather than the paper's
  identity or an unrestricted benchmark release.

## Formal and architectural corrections

- Defined memory state, typed record, candidate, attributable evidence, target
  resolution, controller, transition, provenance, validity, lineage, audit
  event, and application-specific loss.
- Clarified KEEP as preservation or compatible admission without replacement,
  SUPERSEDE as retained-predecessor replacement, and ABSTAIN as refusal to make
  the proposed durable commitment.
- Added a concrete three-evidence example that holds the candidate fixed and
  shows different state consequences.
- Added an architecture flow showing proposal, validation/mutation, audit,
  retrieval, and answer boundaries.
- Separated the generic tested protocol from the evaluated V12 SQLite runtime.
- Corrected claims that implied V12 invoked the generic invariant validator or
  serialized the generic transition event.

## Evaluation and statistical corrections

- Organized evaluation around answerable research questions and separated
  decision, state/lineage, retrieval, and answer layers in a flow diagram.
- Retained exact MGP-6 v4.3 denominators, confusion matrix, component-cluster
  intervals, false-commit decomposition, and cost-sensitive analysis.
- Labeled all public-development comparisons, historical v2 analyses,
  external mappings, incomplete runs, and post-hoc replays with their actual
  status.
- Marked LongMemEval V12 as a final candidate and disclosed its nonterminal
  manifest, stale launcher hash, single model/judge/seed, and lack of
  candidate-level write gold.
- Reconciled the final adjudicated LongMemEval scores to 137/180 for ASK and
  114/180 for naive overwrite.

## MGP-Natural

- Added a dedicated MGP-Natural subsection without presenting it as a current
  result.
- Described two intended tracks based on existing real conversations:
  StudyChat human-AI educational interaction and WikiConv human-human editorial
  discussion.
- Added a workflow diagram from source rights/privacy review through candidate
  mining, redaction, continuity graph construction, protocol freeze, blinded
  independent labeling with evidence-turn citations, adjudication,
  continuity-aware splitting, and track-specific ASK scoring.
- Recorded the v0.1.0 seed's leakage, single-curator status, invalid held-out
  split, and no-score boundary.
- Recorded v0.2.2 as construction software with a private-derived aggregate
  intake only. No construction count is treated as a benchmark denominator.
- Added the required human, legal, privacy, integrity, annotation, adjudication,
  and split gates to limitations and unresolved issues.

## Related work and writing

- Reorganized related work around persistent memory, write policy, temporal
  conflict, provenance, selective prediction, operation/state evaluation, and
  conversational memory evidence.
- Added and verified recent primary references for MemPatch, MemOps, WRIT,
  CareCallMem, and MemStrata.
- Removed benchmark-centered framing, inflated release language, unsupported
  equivalence, generic AI transitions, and em dashes in maintained paper prose.
- Reconciled citations so every bibliography entry is cited and every citation
  resolves.

## Artifacts and auditability

- Updated the paper claim matrix and contribution audit.
- Updated architecture and protocol documentation to state the reference/runtime
  boundary.
- Updated the paper drift checker to enforce ASK-centered abstract fragments and
  the disclosed runtime limitation.
- Added final audit, claim-evidence, changelog, reproducibility, unresolved-
  issue, and machine-readable metrics reports.
- Regenerated and visually inspected the canonical 47-page PDF.
- Completed a clean-commit reproduction and sanitized machine-local paths and
  checkout identity from its public receipt.
