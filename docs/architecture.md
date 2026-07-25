# Architecture

```text
User event
  -> extraction and typed candidate memory
  -> relation / evidence analysis
  -> ASK scorecard or model-backed policy
  -> KEEP | SUPERSEDE | ABSTAIN
  -> validated memory-state transition with lineage
  -> provenance-constrained retrieval
  -> answer generation and evaluation
```

Core modules:

- `src/ask/extraction`: candidate extraction and schema recovery.
- `src/ask/classifier`: relation classification.
- `src/ask/controller`: features, scorecard, temporal/computation helpers, and active policy.
- `src/ask/memory`: records, persistence, and operations.
- `src/ask/pipeline`: end-to-end orchestration.
- `src/ask/baselines`: no-memory, vector, recency, and overwrite baselines.
- `src/ask/eval`: LongMemEval and MGP-6 evaluation.
- `benchmarks/mgp6`: frozen v2 diagnostic, adapters, annotation material, and scorer.
