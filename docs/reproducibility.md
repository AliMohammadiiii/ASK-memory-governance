# Reproducibility contract

The maintained environment is CPython 3.11/3.12. The current local reference
environment is `.venv/bin/python`; Homebrew Python 3.14 is unsupported. Start
from a clean checkout, install `.[dev]`, and run `make check`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
make check
```

`bash scripts/setup_venv.sh` is the equivalent non-destructive bootstrap.
Model, schema, and document extras are optional and are not silently installed
by the offline gate.

Three levels must not be conflated:

- **Offline engineering reproduction:** repository validation, lint, type
  checks, tests, schemas, and package build without credentials.
- **Evidence verification:** claim ledger, raw-output hashes, scorer reruns,
  event replay, coverage, and derived-manifest checks.
- **Experimental replication:** exact public inputs, frozen controls, models,
  judges, external data, and independent annotations. Some components are
  private, third-party, or not yet executed.

A run manifest must identify Git state, environment, inputs, prompts,
configuration, requested and actual model/judge, seed, retry/fallback policy,
coverage, errors, outputs, and hashes. Resumed or dirty runs are disclosed. A
derived audit manifest may add current hashes and anomalies but never rewrites a
historical manifest.

The clean-reproduction gate remains false until a new isolated environment
successfully runs the documented public path from a frozen commit and stores a
machine report. Run `make clean-reproduction` only from a clean frozen commit;
the command creates a fresh virtual environment, applies
`constraints/repro-py312.txt`, runs `make reproduce-public`, and records hashed
command output and the resolved environment.

Before a source release, run `make release-check`, `make verify-claims`,
`make verify-manifest`, `make release-audit`, and `make readiness`. Network or
non-redistributed research data are never silently fetched. Do not pass
credentials on command lines; retain external-data checksums rather than local
absolute paths.

The release builder includes only Git-tracked public candidates and normally
requires a clean worktree. Generated repositories carry a per-file SHA-256
manifest. `--allow-dirty` is for local diagnosis only and cannot support a
publication gate. Benchmark-specific commands are in `reproduce_results.md`.
