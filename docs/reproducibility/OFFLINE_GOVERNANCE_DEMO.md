# Offline governance demonstration

Run `ask-offline-demo` after installing the package, or
`python examples/offline_governance_demo.py` from the repository root. The fixture uses fixed SHA-256 digests and the pure
ASK-MGP adapter; it makes no provider calls and contains no research data.

The script retrieves an exact fixture turn with deterministic SHA-256 baseline
embeddings, records that turn's content digest as evidence, composes each
proposal with a deterministic rule proposal, applies the transition, and
replays both the decision trace and transition event. KEEP preserves the
existing record, SUPERSEDE marks it inactive and retains its predecessor link,
and ABSTAIN leaves state unchanged. Replay verifies the declared
composition-and-transition scope; it does not rerun or validate an LLM
prediction. The output contains no scientific benchmark measurements.

## Code tour and expected output

- Retrieval and evidence identity: `ask.offline_demo.main` uses
  `FakeEmbedder` and `FlatVectorStore`, then hashes the retrieved fixture text.
- Action composition: `ASKMGPAdapter.decide` creates the trace from fixed model
  and rule proposals.
- State changes and lineage: `apply_transition` in `ask.protocol.core` records
  the event and predecessor reference.
- Replay and validation: the demo asserts that both trace replay and transition
  replay reproduce the same action and state.

The run prints one retrieved turn and three action lines (`Keep`, `Supersede`,
`Abstain`). The supersession state shows the prior record inactive and the new
record active with its predecessor pointing to the prior record. KEEP and
ABSTAIN leave the original record active. Digests are deterministic for this
fixture and are not benchmark results.

For historical result qualifications and evidence limits, see the
[`SCIENTIFIC_LIMITATIONS.md`](../SCIENTIFIC_LIMITATIONS.md).
