# ASK memory-governance sample

This is a curated, standalone source snapshot of ASK, an auditable state-
transition protocol for memory updates in language-agent systems. It contains
selected package modules, focused tests, schemas, and a deterministic offline
demonstration. It is not the full research repository or its full experiment
history.

The project was developed by Ali Mohammadi. This public source snapshot derives
from archive revision
[`480ae95287fb9cb75772fe9570c9ecf4ceb2a26f`](docs/PROVENANCE.md). Full source
history and non-public evidence remain in the private archive. NumPy and FAISS
provide vector operations; SQLite provides transactional memory storage.

## Install and run

Supported Python versions are 3.11 and 3.12. Install the selected package and
development dependencies:

```bash
python -m pip install -e '.[dev]'
python -m pip install 'faiss-cpu>=1.8,<2'
ask-offline-demo
```

The offline example uses deterministic synthetic input and a fixed embedding
fixture. It demonstrates retrieval, KEEP/SUPERSEDE/ABSTAIN decisions, evidence
identity, supersession lineage, and replay validation. It makes no provider
calls and reports no scientific benchmark result.

## Focused verification

Run the tests included in this snapshot:

```bash
python -m pytest -q tests
python -m ruff check src tests benchmarks
python -m mypy src/ask
python -m build
```

The curated test suite and package checks are the scope exercised by the
snapshot's CI. The 691-test full-repository check and complete release gate
belong to the private archive and are not claims about this snapshot.

## Scientific evidence boundary

The historical research ledger, raw predictions and judgments, benchmark
inputs, and complete run manifests are not included here. The source archive's
claim-verification run recorded 38 mismatches because registered evidence and
source artifacts were unavailable in the reviewed checkout. This package does
not rerun that verification or reproduce those results. The [limitations
record](docs/SCIENTIFIC_LIMITATIONS.md) preserves relevant validity findings
and qualifications.

## Package layout

- `src/ask/protocol/`: decision traces, transitions, replay, and invariants.
- `src/ask/memory/`: SQLite-backed memory operations and lineage.
- `src/ask/baselines/`: exact vector retrieval and deterministic test embedder.
- `src/ask/offline_demo.py`: runnable provider-free example.
- `tests/`: selected protocol, atomicity, vector, configuration, and replay
  regression tests.
- `docs/`: architecture, operational limits, provenance, and evidence boundary.

This snapshot is provided under the MIT License. It contains no benchmark data.
