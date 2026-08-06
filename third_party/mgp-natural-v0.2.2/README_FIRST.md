# Read this first: corrected full-source repository

This is MGP-Natural v0.2.2. It replaces the earlier sample-era ZIP whose
Makefile did not contain the `full-*` targets.

## Keep raw inputs outside this repository

Set the environment variable to the private directory containing the eleven
source files:

```bash
export MGP_FULL_INPUTS=/path/to/private/full_inputs
```

Do not copy raw StudyChat or WikiConv archives into this repository, Git, or a
public release package.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

## Run the corrected full-source workflow

```bash
make full-reproduce
```

Incremental commands are:

```bash
make full-audit-input
make full-reconstruct-studychat
make full-scan-wikiconv
make full-context-wikiconv
make full-privacy-blind
make annotate-ai-provisional
make full-continuity-splits
make full-validate
make test
make lint
make typecheck
make build
make claim-check-full
make readiness-full
```

The AI annotations are deterministic offline provisional outputs, not human
annotations and not gold. `make package-public` must remain blocked until legal,
privacy, independent human annotation, adjudication, and release approvals are
recorded.

## Verified in the build environment

The corrected implementation was exercised against the supplied full sources:

- StudyChat: 16,851 interactions, 2,214 chats, 203 pseudonymous users.
- WikiConv 2003: 172,286 utterances.
- WikiConv 2018: 3,914,519 utterances, all seven parts.
- Constructed before human review: 431 StudyChat and 54 bounded WikiConv items.
- Full machine validation: pass, with human gates pending.
- Tests: 132 passed; the one ZIP duplicate warning is generated intentionally by
  the tampered-packet negative test.
- Wheel and sdist build: pass and deterministic in two repetitions.

The Ruff diagnostics, strict-mypy input narrowing, local build dependencies,
and runtime-log security-boundary issue reported during the full-source run have
been corrected in v0.2.2. Rerun `make lint`, `make typecheck`, `make build`, and
`make security-scan` in the Python 3.12 environment above. Any remaining
diagnostics must still be treated as failures and fixed rather than bypassed.

