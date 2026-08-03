# Changelog

## Unreleased

- Added the canonical typed ASK protocol, ASK-MGP and ASK-LME adapter contracts,
  deterministic transition replay, schemas, invariant validation, and formal
  counterexample tests.
- Added machine-readable artifact inventory, 25-claim verification ledger,
  additive V12 provenance manifest, release/legal matrices, readiness engine,
  confirmation schemas/tooling, trajectory metrics, and a blocked prospective
  four-family model matrix.
- Reframed the manuscript and README so ASK is the protocol/audit contract,
  controllers are implementations, and MGP-6 is controlled evidence rather
  than the complete contribution.
- Added reproducibility constraints, container recipe, clean-environment runner,
  venue administration templates, official-requirements snapshot, and expanded
  CI/local commands.
- Preserved unresolved legal, authorship, independent-annotation, external-run,
  venue-template, and clean-commit gates as explicit NO-GO blockers.

## Unreleased

- Made the Makefile and CI use module-based Python tooling with a single
  offline release gate.
- Added release-tooling regression tests and fail-closed clean-worktree checks.
- Restricted public release candidates to Git-tracked files.
- Added version-consistency, canonical-data, repository-boundary, and secret
  validation.
- Added built-wheel metadata and packaged-resource verification.
- Consolidated setup scripts and declared the optional DOCX builder dependency.
- Added a maintained documentation index and separated current guidance from
  historical evidence snapshots.
- Removed generated preview renders, copied presentation figures, and duplicate
  MGP-6 dataset files from the source tree.

## 0.2.0 — 2026-07-13

- Reconstructed the full Git-ready repository from the authoritative ASK source archive.
- Integrated the frozen MGP-6 v2 benchmark and separated human from model annotations.
- Removed caches, local databases, backup files, generated package metadata, and large historical runs.
- Added CI, public repository metadata, OpenRouter configuration, reproducibility state files, and repository validation.
- Corrected MGP-6 scorer normalization and symmetric memory-value canonicalization.
- Added regression tests for action aliases and scorer canonicalization.
- Made non-redistributed LongMemEval fixture tests skip explicitly rather than fail mysteriously.
