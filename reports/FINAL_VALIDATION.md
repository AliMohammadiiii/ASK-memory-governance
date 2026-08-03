# Final validation record

Date: 2026-08-02. Environment: CPython 3.12.12 in `.venv`. Working tree is
intentionally dirty with the changes from this audit; no commit or push was
performed.

| Command | Exit | Result |
|---|---:|---|
| `make check PYTHON=.venv/bin/python` | 0 | repository/secret scan, Ruff, formatting, mypy, compile, shell syntax, 572 tests passed; 14 documented optional skips |
| `.venv/bin/python -m pytest -q` | 0 | 572 passed, 14 optional skips |
| `make verify-claims PYTHON=.venv/bin/python` | 0 | 26 verified claims, zero unexplained mismatch |
| `make verify-manifest PYTHON=.venv/bin/python` | 0 | V12 derived hashes match; status remains `DERIVED_AUDIT_ONLY` |
| `make inventory PYTHON=.venv/bin/python` | 0 | 906 artifact rows; no selected evidence missing |
| `make validate-public-data validate-traces validate-experiments verify-paper-artifacts PYTHON=.venv/bin/python` | 0 | declared boundaries, protocol schema/tests, four-family dry matrix, and 18 paper fragments passed |
| `make confirmation-dry-run PYTHON=.venv/bin/python` | 0 | 7 schema/blinding safeguards passed; no labels or inference |
| `latexmk -pdf ... main.tex` | 0 | anonymous venue-neutral PDF built, 44 pages |
| `scripts/release/audit_bibliography.py` | 0 | citation and bibliography audit passed |
| `make anonymous-scan PYTHON=.venv/bin/python` | 0 | manuscript source-text scan passed; final venue archive scan still required |
| `make readiness PYTHON=.venv/bin/python` | 0 | evaluator ran and returned `NO_GO` |
| `make clean-reproduction PYTHON=.venv/bin/python` | 2 | correctly blocked because the working tree is not a frozen clean commit |
| `make build-paper-tmlr` | 2 | canonical official-template source absent under `paper/tmlr/` |
| `make build-paper-jmlr` | 2 | canonical official-template source absent under `paper/jmlr/` |
| `make confirmation-freeze` | 2 | correctly blocked pending independent human/legal review |

No paid inference, external service execution, hidden-set rescoring for model
selection, commit, push, archive publication, or human/rights decision occurred.
