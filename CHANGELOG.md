# Changelog

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
