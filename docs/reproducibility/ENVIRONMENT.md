# Environment scope

## Supported Python

The package metadata supports CPython 3.11 and 3.12. CI runs both versions.
Python 3.14 cache files or a local 3.14 interpreter do not expand support.

## Dependency groups

- Base dependencies support the package, schemas, templates, and numeric work.
- `dev` contains tests, Ruff, mypy, package build, and local hook tooling.
- `schema` contains LinkML generation tools.
- `ml` contains model, embedding, and vector-store dependencies.
- `pai` contains the optional Pydantic AI adapter.
- `documents` contains DOCX generation support.

No optional group is installed by the offline runtime package. Constraint files
under `constraints/` define the clean-reproduction environment where available.

The maintained Python 3.12 ML stack is locked in `constraints/ml-py312.txt`.
Install it with `make setup-ml PYTHON=.venv/bin/python`, then run
`make hf-compat PYTHON=.venv/bin/python`. The lock records Transformers 5.14.1,
Sentence Transformers 5.6.1, PyTorch 2.13.0, and their transitive dependencies.

External memory-system adapters use the independent
`constraints/external-baselines-py312.txt` lock and `make setup-external`. That
environment retains Transformers 4.57.6 for MemoryOS compatibility and must not
be combined with the maintained ML environment or historical result directories.

## Platform and external services

CPU-only offline checks do not require a database, network, GPU, or provider.
Model-backed runs must record hardware, model revision where exposed, provider,
requested and observed identifiers, fallback behavior, and relevant library
versions. An external dataset is supplied through a configured path and verified
by hash. It is not copied into Git for convenience.

Use environment variables or a secret manager for credentials. The repository
contains `.env.example`, but it never reads or publishes a real `.env` file.
