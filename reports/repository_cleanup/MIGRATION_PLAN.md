# Repository migration plan

Date: 2026-08-05

## Scope

The package, benchmark layout, experiment evidence, paper, and thesis already
have distinct roots. The migration therefore avoids a broad source rewrite.
It addresses the confirmed defects: missing cleanup records, one ambiguous
backup, scattered architecture and reproducibility entry points, absent prompt
status metadata, incomplete local hooks and CI separation, a generated advisor
tree in the workspace, prose leakage checks, and a thesis source error.

## Planned changes

1. Move the LaTeX v11 backup to `docs/history/paper/` and preserve its hash.
2. Put repository architecture, authority, tree, and reproducibility documents
   under dedicated directories and update current references.
3. Register prompt purpose, status, path, hash, experiment relations, and
   supersession without renaming prompt bytes used by reported runs.
4. Add deterministic inventory, prose, prompt, and document-path checks.
5. Add dev-only pre-commit tooling and pin CI actions to full commit hashes.
6. Make the local embedding server bind to loopback and require explicit remote
   code authorization.
7. Remove regenerable build and advisor-handoff output after validation.
8. Preserve experiment evidence and exact duplicate pairs that have distinct
   roles.

## Validation

Each moved file is recorded in `MIGRATION_MAP.csv` with its original SHA-256.
Claims, manifests, repository validation, package builds, tests, prompt hashes,
document paths, paper compilation, and thesis compilation run after changes.
External, private, paid, GPU, and human workflows remain `NOT RUN` unless their
prerequisites are supplied.
