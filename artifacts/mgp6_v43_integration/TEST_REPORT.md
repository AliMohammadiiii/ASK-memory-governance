# MGP-6 v4.3 integration test report

## Verified release and local checks

- Outer handoff verifier, nested release verifier (five internal archives),
  outer/nested ZIP CRC checks, and the final pre-install CRC check: PASS.
- `.venv/bin/python -m pip install -e '.[dev]'`: PASS; development
  dependencies, including Mypy, are installed in the repository virtualenv.
- `git diff --check`: PASS.
- `.venv/bin/ruff check .`: PASS.
- `.venv/bin/pytest`: PASS — 545 passed, 0 failed, 11 skipped; 19 focused
  MGP-6 v4.3 tests cover release invariants, public-only model views, strict
  prediction coverage, deterministic/resume-safe writing, metrics, private
  ignore protection, and frozen-control authorization binding.
- `.venv/bin/mypy --follow-imports=skip src/ask/controller src/ask/memory src/ask/eval/mgp6.py src/ask/eval/mgp6_schema.py src/ask/eval/mgp6_v43.py`:
  PASS — exact GitHub Actions scope, 16 source files, no issues.
- `.venv/bin/mypy src/ask scripts/run_mgp6_v43.py scripts/score_mgp6_v43.py scripts/freeze_mgp6_v43.py`:
  PASS — extended local Mypy scope, no issues.
- `python3 scripts/validate_repository.py`: PASS — structure and secret scan
  OK.
- `env TMPDIR=<local-temporary-directory> .venv/bin/python -m build`: PASS —
  source distribution and wheel built. The first direct invocation could not
  create a system temporary directory while the volume was full; no package
  error occurred, and the clean local temporary-directory rerun succeeded.
- `latexmk -pdf -outdir=<temporary directory> main.tex`: PASS; tracked paper
  build outputs were not replaced.

## Executed development-only runs

The deterministic train fixture and three-item public-train provider smoke
passed. All model-backed baselines, the rules controller, the initial live
controller, the selected public-indexed-evidence controller, and its required
ablations completed on public dev only. The selected controller and all four
ablations had strict 180-item coverage with no hidden-gold access. Full
protocol and public-dev metrics remain in `DEV_EXPERIMENT_REPORT.md`.

No hidden prediction or private scoring run has been performed.

## Remote CI and freeze evidence

GitHub Actions CI run [`30189412351`](https://github.com/AliMohammadiiii/KSA-memory-governance/actions/runs/30189412351)
completed successfully for
`af12517a15c9d9af4bb3bf95f7caee7330e6b243` (`Gate MGP-6 v4.3 hidden runs on
frozen controls`). That SHA is the frozen runtime-control commit and is bound
by both final hidden-control artifacts. At freeze time the tracked worktree was
clean; only the separately classified historical untracked paths remained.

`FINAL_HIDDEN_CONFIG.json` and `FINAL_HIDDEN_RUN_AUTHORIZATION.json` were then
validated as JSON and by a regression test. The authorization is true only for
one complete prediction-generation run; it enforces exact runtime controls and
requires complete prediction hashing before separate local-private scoring.
