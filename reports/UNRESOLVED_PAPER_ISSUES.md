# Unresolved Paper Issues

Date: 2026-08-06

Only dependencies that cannot be resolved from the current repository are
listed here.

## Publication and evidence blockers

1. **MGP-6 v4.3 redistribution license.** No public redistribution license has
   been selected. The paper may describe and score the controlled diagnostic,
   but the dataset must not be advertised as an unrestricted public release.

2. **LongMemEval V12 manifest finalization.** The adjudicated controller and
   baseline outputs are complete, but the historical top-level manifest remains
   `status: running` with `exit_code: 1`. The homogeneity report also records a
   stale hash for `scripts/evaluation/run_longmemeval_final.sh`. Historical
   evidence must not be rewritten. A new derived finalization record with parent
   hashes is required if the run is promoted beyond “final candidate.”

3. **LongMemEval write labels and replication breadth.** The 180-question slice
   has answer judgments but no gold ASK action for each extracted candidate.
   The experiment uses one answer model, one judge, one seed, and one slice.
   Additional models, judges, seeds, and trajectory-level annotation would be
   required for broad generalization.

4. **Runtime provenance normalization.** The evaluated SQLite runtime stores
   type, status, validity, and lineage, while source session and turn provenance
   remain in pipeline traces. It does not emit the generic `TransitionEvent` or
   call the generic invariant validator. Closing this gap requires a new
   implementation and new evaluation, not a prose change.

5. **MGP-Natural human-human track.** The current WikiConv-derived material is a
   private construction input. Original-source archive integrity, attribution,
   redistribution rights, manual privacy review, protocol freeze, independent
   labels with evidence-turn citations, adjudication, and contributor/page
   continuity splits remain open.

6. **MGP-Natural human-AI track.** The current StudyChat-derived material is a
   private construction input. Original-source archive integrity, consent and
   rights review, privacy approval, protocol freeze, independent labels,
   adjudication, and conversation/participant continuity splits remain open.

7. **MGP-Natural v0.1.0 replacement.** The 36-item seed has single-curator
   provisional labels, complete leakage through relation/source fields, and two
   continuity components of sizes 35 and 1. Its 24/6/6 split is not valid held-
   out evidence and cannot be repaired by rescoring the same packet.

## Not blockers for the current bounded paper

- MGP-Natural is present as a prospective evidence track, not a reported result.
- MGP-6 v2 remains useful only as documented construct-failure evidence.
- Development-only ablations and external mappings are labeled as such and are
  not used for hidden-set superiority claims.
