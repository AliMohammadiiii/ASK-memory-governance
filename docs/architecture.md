# ASK architecture

ASK is a write-governance contract, not a benchmark or one controller. It
separates these responsibilities:

1. Candidate formation produces a typed candidate and source context.
2. Target resolution selects a relevant active prior when one exists.
3. Evidence and relation assessment produce controller inputs.
4. A policy proposes Keep, Supersede, or Abstain.
5. A transition component, not the proposing model, mutates storage.
6. Retrieval distinguishes active state from retained history.
7. Audit and evaluation reconstruct decisions and score action, state, lineage,
   retrieval, and answer outcomes separately.

The intended flow is:

```text
dialogue/event -> candidate -> target/evidence/relation -> ASK controller
-> transition plan -> invariant or transaction checks -> state + audit record
-> active or historical retrieval -> downstream answer
```

## Two implemented paths

`src/ask/protocol/` is the normative executable reference core. It provides
content-addressed evidence and configuration identities, adapter-declared replay
scope, immutable transition events, deterministic transitions, and invariant
validation for versioned single-slot, multi-record, and temporal-event modes.
`tests/test_ask_protocol.py` is the primary conformance evidence.

The evaluated LongMemEval runtime is implemented in `src/ask/pipeline/`,
`src/ask/controller/`, and `src/ask/memory/`. For each benchmark question it
rebuilds an in-memory SQLite state, extracts candidates from supporting
sessions, resolves a prior and relation, applies the five-feature scorecard,
and lets the orchestrator invoke database operations. SQLite supersession is
transactional, retains the prior row, creates a successor link, and changes
active status. Normal retrieval filters out superseded rows; explicit
historical queries traverse retained lineage.

These paths share ASK action semantics but are not the same transition runtime.
The LongMemEval orchestrator does not call the generic invariant validator and
does not emit the generic transition event. Its action log records features,
scores, thresholds, actions, rationales, and record identifiers, which is enough
to replay final scorecard decisions. Session and turn provenance remain in the
pipeline trace. Evidence digests and before/after state digests belong to the
reference protocol path.

MGP-6 is a controlled diagnostic, LongMemEval is a downstream evaluation
instrument, and MGP-Natural is a quarantined natural-evidence track without
independent gold. None defines ASK. Benchmark labels must never become
model-facing through an adapter.
