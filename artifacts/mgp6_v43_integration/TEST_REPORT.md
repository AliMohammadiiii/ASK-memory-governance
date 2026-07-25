# MGP-6 v4.3 integration test report

## Release integrity

- Outer handoff verifier: PASS.
- Nested release verifier: PASS (five internal archives).
- Outer and nested ZIP CRC checks: PASS.
- Final pre-install nested ZIP CRC check: PASS.

## Local CI-equivalent checks

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pip install -e '.[dev]'` | PASS — development dependencies, including Mypy, available in the repository virtual environment. |
| `python3 scripts/validate_repository.py` | PASS — repository structure and secret scan OK. |
| `.venv/bin/pytest` | PASS — 534 passed, 0 failed, 11 skipped. |
| `.venv/bin/ruff check .` | PASS. Immutable historical archive roots and release-source provenance are narrowly excluded from lint discovery. |
| `.venv/bin/mypy --follow-imports=skip src/ask/controller src/ask/memory src/ask/eval/mgp6.py src/ask/eval/mgp6_schema.py src/ask/eval/mgp6_v43.py scripts/run_mgp6_v43.py` | PASS — no issues found in 17 source files. |
| `.venv/bin/python -m build` | PASS — source distribution and wheel built. |
| `latexmk -pdf -outdir=<temporary directory> main.tex` | PASS — paper compiled without replacing tracked build outputs. |
| `python3 scripts/run_mgp6_v43.py ... --limit 3 --action ABSTAIN` twice | PASS — deterministic train engineering fixture exercised serialization, parsing, persistence, resume behavior, and metric calculation; no provider call and no scientific result. |
| `.venv/bin/python scripts/run_mgp6_v43.py --limit 2 --action ABSTAIN --out /tmp/mgp6_v43_runner_smoke` | PASS — runner hardening smoke verified manifest, raw-response, and prediction writing without any provider call. |

## CI status

The GitHub Actions workflow now includes the v4.3 evaluator in its Mypy scope.
The complete local command sequence mirrors that workflow and passed. No remote
GitHub Actions run is claimed because this integration has not been pushed.

No live-provider, development-selection, hidden-prediction, or private-scoring
experiment has run.

## Integration commit and worktree state

- Integration base commit: `41f7ceeb38c971874b52578c4b622a704b992715`
  (`Integrate MGP-6 v4.3 final release`).
- Runner hardening commit: `86e3674` (`Harden MGP-6 v4.3 OpenRouter smoke runner`).
- Immediately after that commit, the tracked worktree was clean. The only
  remaining `git status --short` entries were the deliberately preserved,
  classified historical untracked paths; no private v4.3 path was visible.
