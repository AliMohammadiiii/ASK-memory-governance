# Reproducibility contract

ASK distinguishes engineering reproduction, evidence verification, and
experimental replication.

Engineering reproduction installs the package and executes offline checks with
no credential or external dataset. Evidence verification recomputes registered
claims, hashes, metrics, traces, and manuscript fragments. Experimental
replication also requires the declared inputs, model and judge versions,
provider behavior, prompts, configuration, seeds, and any independent human
work. Provider-hosted output cannot be promised as byte-identical when the
provider can revise a model behind an unchanged identifier.

The maintained interpreter range is CPython 3.11 and 3.12. The local reference
interpreter is `.venv/bin/python`. System Python 3.14 is outside the supported
range.

Start with `QUICKSTART.md`. Environment scope is in `ENVIRONMENT.md`. The
source-to-claim chain is in `RESULT_PROVENANCE.md`. Benchmark-specific commands
and external-data limits remain in `../reproduce_results.md`.

A run manifest must record Git state, environment, inputs, prompt and
configuration hashes, requested and observed model or judge identifiers, seed,
retry and fallback policy, coverage, errors, outputs, and output hashes. A
resumed or dirty run must say so. A derived audit manifest may add current
hashes and anomaly notes but does not rewrite its parent.

Before a source release, run:

```bash
make release-check PYTHON=.venv/bin/python
make verify-claims PYTHON=.venv/bin/python
make verify-manifest PYTHON=.venv/bin/python
make release-audit PYTHON=.venv/bin/python
make readiness PYTHON=.venv/bin/python
```

The release builder reads Git-visible public candidates and normally requires
a clean worktree. `--allow-dirty` exists for local diagnosis and cannot support
a publication decision. Network data is never fetched by an offline gate.
Credentials must not appear in command lines, manifests, reports, or logs.
