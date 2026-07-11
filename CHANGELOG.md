# Changelog

## 0.2.0 — 2026-07-12

- Reconstructed the full Git-ready repository from the authoritative KSA source archive.
- Integrated the frozen MGP-6 v2 benchmark and separated human from model annotations.
- Removed caches, local databases, backup files, generated package metadata, and large historical runs.
- Added CI, public repository metadata, OpenRouter configuration, reproducibility state files, and repository validation.
- Corrected MGP-6 scorer normalization and symmetric memory-value canonicalization.
- Added regression tests for action aliases and scorer canonicalization.
- Made non-redistributed LongMemEval fixture tests skip explicitly rather than fail mysteriously.
