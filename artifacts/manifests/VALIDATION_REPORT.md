# Validation report

Generated: 2026-07-12

## Verified checks

- Offline tests: **420 passed, 14 skipped**.
- MGP-6 v2 strict validation: **180 examples, 0 errors**.
- Ruff: passed for `src`, `tests`, `scripts`, and `benchmarks`.
- Mypy: passed for the typed KSA core (controller, memory, MGP-6 evaluator/schema).
- Repository structure and secret scan: passed.
- Wheel build: `ksa_memory_governance-0.2.0-py3-none-any.whl`.
- Wheel SHA-256: `37b16685f019b3a03876bd842d9e70abfbcf7fbcba7ba17ca92974fb19634fd5`.

## Documented skips

- FAISS-dependent tests require the optional `ml` dependency group.
- LongMemEval computation-replay fixtures are not redistributed.
- MiniLM smoke tests are opt-in because of Apple-Silicon runtime risk.

## Not executed in this build

- Fresh OpenRouter Qwen/Gemma hosted-model experiments.
- External Letta/Mem0/MemOS/Graphiti service runs.
- Full LongMemEval transfer runs requiring external data.
