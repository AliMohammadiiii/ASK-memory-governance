# Reproducibility

## Supported environment

ASK supports CPython 3.11 and 3.12. Start from a clean checkout:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

`bash scripts/setup_venv.sh` performs the same bootstrap without deleting an
existing environment. Model, schema, and document tooling are optional extras
and are not needed for the offline verification gate.

## Verification gates

The fast offline gate is:

```bash
make check
```

Before a source release, run:

```bash
make release-check
```

The release gate covers repository metadata and secret scanning, lint, supported
type checking, bytecode compilation, shell syntax, the complete test suite,
strict MGP-6 v2 data validation, package build, and bibliography audit. Network
or non-redistributed data is not silently fetched.

## Run provenance

Every model-backed run must record:

- Git commit and dirty-state flag;
- exact input and configuration hashes;
- requested and actual model/judge identifiers;
- provider and fallback policy;
- prompt or prompt-bundle hash;
- random seed and scorer version;
- prediction coverage, failures, retries, and invalid responses.

Do not pass credentials on the command line. Keep external datasets outside the
repository and record checksums rather than machine-local paths or raw data.

## Release reproducibility

The release builder includes only Git-tracked public candidates and requires a
clean worktree. Generated repositories include a file manifest with size and
SHA-256 for every included file. `--allow-dirty` is limited to local validation
and must not be used for a published artifact.

Benchmark-specific commands and evidence eligibility are documented in
`reproduce_results.md`.
