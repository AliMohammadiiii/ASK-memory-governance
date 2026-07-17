# Validation report

Generated: 2026-07-15

## Verified checks

- Offline tests: **472 passed, 11 documented optional skips**.
- MGP-6 v2 strict validation: **180 examples, 0 errors**.
- Ruff: passed for the complete repository.
- Mypy: passed for **60 source files**.
- MGP-6 validity audit: regenerated; conflict type alone reaches **1.000 held-out accuracy**, so v2 policy scores are diagnostic.
- Repository structure and secret scan: passed.
- Extracted public repository: sdist and universal wheel build passed.
- Fresh isolated environment: wheel installed with `--no-deps`, `ksa` imported,
  and all four packaged configuration/schema resources were present.
- Release archive: internal checksums, outer checksum, nested ZIP integrity, and
  extracted-copy smoke gates passed.

## Documented skips

- LongMemEval computation-replay fixtures are not redistributed.
- MiniLM smoke tests are opt-in because of Apple-Silicon runtime risk.

## Not executed in this build

- Fresh OpenRouter Qwen/Gemma hosted-model experiments.
- External Letta/Mem0/MemOS/Graphiti service runs.
- Full LongMemEval transfer runs requiring external data.
- The proposed seven-arm single-session-preference correction experiment.
- Role-separated MGP-6 v3 construction, three-human annotation, and hidden confirmation runs.
