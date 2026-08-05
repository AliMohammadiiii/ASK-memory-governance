# Reproducibility

## Environment

The package targets Python 3.11 and 3.12. Runtime dependencies are intentionally small: PyYAML and jsonschema. Development validation is configured for pytest, Ruff, mypy, and build. In this execution only Python 3.13.5 and pytest were available; Ruff, mypy, the `build` frontend, and Python 3.11/3.12 were recorded as unavailable rather than passed. The offline fallback emitted both a wheel and source distribution.

## Determinism

All derived JSON is serialized with stable key ordering and no NaN values. JSONL rows use canonical serialization. Input, output, packet, and release files are hashed with SHA-256. Split assignment, bootstrap sampling, perturbation selection, and fixture generation use pinned seeds. Stable sorting is applied before hashing or assignment.

Private blind IDs depend on a secret and are deterministic only for the same pinned source, transformation, protocol, and private reveal record. The secret is not part of public reproduction.

## Commands

Install and validate:

```bash
make install
make check
```

Rebuild the available sample-derived pipeline:

```bash
make reproduce
```

Build distributions and run the public clean-room smoke test:

```bash
make build
make clean-reproduce
```

Individual targets are documented in the root `Makefile`. No command publishes, uploads, accepts gated terms, or calls a paid model API.

## Input pinning

The supplied archive and every archive member are recorded in `reports/input_manifest.json`. Full-data runs must create a new manifest rather than overwrite evidence for the sample derivative. WikiConv downloads require an explicit per-artifact spec; expected size and SHA-256 are checked when available.

## Public versus private reproduction

Public clean-room reproduction uses only synthetic or rights-cleared fixtures. It verifies package installation, public command execution, deterministic output hashes, and the absence of private paths. Reproducing natural candidate pools additionally requires authorized source data and private transformations; this is documented but not redistributed.

## Run records

Model and baseline run records must include exact model and provider identifiers, revision, prompt hash, code hash, random seed, decoding parameters, tools, timestamp, retry and fallback policies, input manifest hash, output hash, cost when applicable, and failure counts. Silent fallback is prohibited.

## Non-deterministic upstreams

External model providers and mutable source URLs can change. A run is reproducible only when its model revision and source artifact are pinned or when the limitation is stated. Acquisition fails closed if an expected hash or size changes.

## Clean-room criterion

The clean-room test creates a temporary virtual environment, installs the built wheel, copies only public fixtures, invokes the installed CLI, verifies expected hashes, scans generated paths, and records Python, platform, and dependency versions. Private and raw inputs must not be required. The current run used `--no-deps` because the offline package index could not resolve the declared dependencies; this limitation is preserved in the report.

