# ASK architecture

ASK separates five responsibilities:

1. **Candidate formation** produces a typed candidate and evidence references.
2. **Policy/controller** proposes Keep, Supersede, or Abstain. It may be a
   scorecard, rule system, model, or guarded composition.
3. **Adapter** maps system-specific observations into the canonical ASK trace
   and declares exactly what can be replayed.
4. **Transition engine** applies storage-mode-specific, deterministic state
   changes while retaining predecessor records.
5. **Audit layer** validates evidence/configuration digests, action invariants,
   lineage, and replay equivalence.

`src/ask/protocol/` is the normative executable core. Existing extraction,
classification, controller, memory, and evaluation modules remain system
implementations around that contract.

The end-to-end flow remains:

```text
user event -> typed candidate -> relation/evidence analysis -> policy proposal
-> ASK adapter and trace -> Keep | Supersede | Abstain -> validated transition
-> provenance-constrained retrieval -> answer generation and evaluation
```

Core implementation modules are `src/ask/extraction`, `classifier`,
`controller`, `protocol`, `memory`, `pipeline`, `baselines`, and `eval`.
Benchmark contracts and scorers are under `benchmarks/`; protocol adapters must
not make benchmark labels model-facing.
