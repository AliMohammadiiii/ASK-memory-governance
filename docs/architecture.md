# Architecture

```text
User event
  -> extraction and typed candidate memory
  -> relation / evidence analysis
  -> KSA scorecard or model-backed policy
  -> KEEP | SUPERSEDE | ABSTAIN
  -> validated memory-state transition with lineage
  -> provenance-constrained retrieval
  -> answer generation and evaluation
```

Core modules:

- `src/ksa/extraction`: candidate extraction and schema recovery.
- `src/ksa/classifier`: relation classification.
- `src/ksa/controller`: features, scorecard, temporal/computation helpers, and active policy.
- `src/ksa/memory`: records, persistence, and operations.
- `src/ksa/pipeline`: end-to-end orchestration.
- `src/ksa/baselines`: no-memory, vector, recency, and overwrite baselines.
- `src/ksa/eval`: LongMemEval and MGP-6 evaluation.
- `benchmarks/mgp6`: frozen v2 diagnostic, adapters, annotation material, and scorer.
