# Offline reproduction quickstart

From a clean checkout with CPython 3.11 or 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
make check PYTHON=.venv/bin/python
make release-check PYTHON=.venv/bin/python
```

The first command suite checks repository hygiene, formatting, lint, supported
typing, compilation, tests, shell syntax, prose, prompt hashes, and document
paths. The release suite also validates data and builds the package.

Run the public MGP-6 smoke path without inference:

```bash
make smoke PYTHON=.venv/bin/python
```

Verify registered claims and public/private declarations:

```bash
make verify-claims verify-manifest validate-public-data \
  validate-traces validate-experiments verify-paper-artifacts \
  PYTHON=.venv/bin/python
```

External model execution is opt-in. Do not add a credential or private dataset
to reproduce the offline slice.
