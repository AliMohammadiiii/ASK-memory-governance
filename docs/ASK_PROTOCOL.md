# ASK protocol contract

## Decision semantics

- **Abstain:** commit no candidate and preserve the complete prior state.
- **Keep:** preserve the compared prior. In multi-record stores only, a clearly
  separate candidate may be admitted when the event explicitly records that
  mode; single-slot Keep preserves the full state.
- **Supersede:** require an active prior and a candidate, retain the prior as
  inactive, create an active successor, and point the successor to the exact
  predecessor.

ASK supports versioned single-slot, multi-record, and temporal-event storage.
It does not require a particular predictor, database, embedding model, or
benchmark. Every event binds action, storage mode, before/after state digests,
evidence digest, configuration identity, candidate/prior/result identifiers,
and predecessor lineage. `schema/ask_transition_event.schema.json` is the
wire-level event schema.

The reference engine rejects duplicate IDs, dangling predecessors, lineage
cycles, multiple active records in single-slot mode, action/trace divergence,
and digest mismatches. Its scope is auditability and transition correctness,
not a guarantee that a controller chose the semantically correct action.
