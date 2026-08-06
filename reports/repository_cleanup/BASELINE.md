# Repository cleanup baseline

Captured on 2026-08-05 before cleanup edits.

## Git and workspace state

- Git root: repository root (`.`)
- Starting branch: `main`
- Cleanup branch: `chore/repository-modernization`
- Starting commit: `2452e97a9992779d28fd202b3b91a9c25ae91fab`
- Tracked files: 897
- Tracked plus non-ignored worktree files: 1,096
- Working-directory size: 17 GB
- Supported local interpreter: CPython 3.12.12 at `.venv/bin/python`
- System interpreters observed: CPython 3.14.6 through `python3`; no `python` executable

The starting worktree contained 24 modified tracked files and non-ignored
untracked MGP-Natural inputs, implementation, tests, reports, a benchmark ZIP,
third-party software, and temporary material. These changes predate the cleanup
branch and are treated as user-owned input. The exact paths and hashes are in
`baseline_inventory.csv`.

## Size and hygiene observations

The repository footprint is dominated by ignored local data. Tracked files are
small: the largest tracked file is `claims/source_inventory.json` at 600,626
bytes. No tracked Python bytecode, cache directory, build directory, `dist/`,
egg-info, or expanded `advisor_handoff/` path was found. The ignored local
`advisor_handoff/` directory occupies about 20 MB and is generated evidence,
not a second tracked source tree.

One tracked backup was found:
`paper/paper_1/sections/08_downstream_analysis.tex.bak_v11`. Its disposition is
`ARCHIVE` pending a hash and reference check.

Six byte-identical pairs were found. None is classified as deletable solely by
hash because each may have a distinct experiment, manuscript, packaging, or
typing role:

- full ablation and reference-controller predictions;
- full ablation and reference-controller reports;
- two paper/report figure pairs;
- the empty `tests/__init__.py` and `src/ask/py.typed` markers;
- `thesis/references.bib` and `thesis/latex/references.bib`.

## Baseline validation

The offline release gate passed. Ruff lint and format checks passed, mypy passed
for the supported scope, all shell scripts parsed, the strict MGP-6 data check
passed, and the package build and wheel inspection passed. Pytest reported 599
passed and 14 documented skips.

Claim verification passed for 26 claims. The derived LongMemEval manifest,
public/private boundary declaration, ASK protocol tests, prospective model
matrix, paper fragment check, anonymity scan, and MGP-6 dry-run passed. The
publication readiness decision remains `NO_GO` because external human and legal
gates are open.

The paper compiled to 44 pages. The thesis build failed in
`thesis/latex/chapters/09_validity_limitations.tex` at line 88 because an
unescaped ampersand was parsed as a table separator. Compilation stopped with
63 unresolved citations. This is a pre-cleanup failure.

A clean CPython 3.12 environment successfully installed both the wheel and the
editable project. `import ask` returned version `0.2.0` in both cases.
`pre-commit` was unavailable in the starting environment.

Machine-readable command results are in `baseline_checks.json`. Generated
baseline reports use repository-relative paths and contain no credential values.
