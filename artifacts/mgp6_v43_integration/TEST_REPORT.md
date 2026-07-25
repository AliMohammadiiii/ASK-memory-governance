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
| `.venv/bin/pytest` | PASS — 535 passed, 0 failed, 11 skipped (latest run after the v4.3 system-label guard). |
| `.venv/bin/ruff check .` | PASS. Immutable historical archive roots and release-source provenance are narrowly excluded from lint discovery. |
| `.venv/bin/mypy --follow-imports=skip src/ask/controller src/ask/memory src/ask/eval/mgp6.py src/ask/eval/mgp6_schema.py src/ask/eval/mgp6_v43.py scripts/run_mgp6_v43.py` | PASS — no issues found in 17 source files. |
| `.venv/bin/python -m build` | PASS — source distribution and wheel built. |
| `latexmk -pdf -outdir=<temporary directory> main.tex` | PASS — paper compiled without replacing tracked build outputs. |
| `python3 scripts/run_mgp6_v43.py ... --limit 3 --action ABSTAIN` twice | PASS — deterministic train engineering fixture exercised serialization, parsing, persistence, resume behavior, and metric calculation; no provider call and no scientific result. |
| `.venv/bin/python scripts/run_mgp6_v43.py --limit 2 --action ABSTAIN --out /tmp/mgp6_v43_runner_smoke` | PASS — runner hardening smoke verified manifest, raw-response, and prediction writing without any provider call. |
| `python3 scripts/run_mgp6_v43.py ... --provider openrouter --model-id qwen/qwen3.5-9b --limit 3 --reasoning-effort none --parse-retry-max-attempts 2` | PASS — public train live-provider smoke wrote 3 predictions; 0 failures, 0 parse retries, 0 invalid responses, 1557 prompt tokens, 24 completion tokens, hidden gold not accessed. |
| `python3 scripts/run_mgp6_v43.py ... --input benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl --provider openrouter --model-id qwen/qwen3.5-9b --reasoning-effort none --parse-retry-max-attempts 2` | PASS — completed public-dev `decision_zero_shot` execution: 180 strict-coverage predictions, 180 valid JSON responses, 0 failures, 0 retries, and hidden gold not accessed. Aggregate development metrics are in `DEV_EXPERIMENT_REPORT.md`. |
| `.venv/bin/pytest tests/test_mgp6_v43.py` after the system-label guard | PASS — 9 passed. The public decision runner rejects an unimplemented historical label instead of misrepresenting it as a distinct v4.3 system. |

## CI status

The GitHub Actions workflow now includes the v4.3 evaluator in its Mypy scope.
The complete local command sequence mirrors that workflow and passed. No remote
GitHub Actions run is claimed because this integration has not been pushed.

One development-selection candidate (`decision_zero_shot`) has run and is
documented separately. It is not selected for final hidden evaluation. No
hidden-prediction or private-scoring experiment has run. The live-provider
smoke above used public train records only and is not reported as system
performance.

The full repository suite was also re-run after recording the dev result and
passed: 535 passed, 11 skipped. The v4.3 decision runner's historical system
labels are guarded until distinct adapters exist; the remaining configurations
are therefore not yet executable comparisons.

## Integration commit and worktree state

- Integration base commit: `41f7ceeb38c971874b52578c4b622a704b992715`
  (`Integrate MGP-6 v4.3 final release`).
- Runner hardening commit: `86e3674` (`Harden MGP-6 v4.3 OpenRouter smoke runner`).
- Immediately after that commit, the tracked worktree was clean. The only
  remaining `git status --short` entries were the deliberately preserved,
  classified historical untracked paths; no private v4.3 path was visible.
