# Trajectory Evaluation Protocol

A trajectory is an ordered sequence of candidates over one principal, scope, and slot or a documented lineage-connected slot family. Applying a predicted action yields a derived standing state after every step.

## Required natural trajectory fields

- trajectory ID and track;
- ordered blind item IDs;
- initial standing state;
- gold action and resulting state per step;
- evidence and lineage edges;
- continuity component; and
- final adjudicated state.

## Metrics

The evaluator reports first incorrect write, downstream state corruption length, stale-state persistence, recovery after a later correction, repeated abstention, improper overwrite, lineage breakage, evidence loss, and final-state exactness. Errors are traced to the first causative step instead of treating every downstream mismatch as independent.

## Current boundary

The repository includes a versioned schema, evaluator, and synthetic tests. No natural adjudicated trajectories exist, so trajectory experiments are not complete and no trajectory result may enter the paper.

