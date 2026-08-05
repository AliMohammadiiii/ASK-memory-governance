# Changelog

## 0.2.2 - 2026-08-04

- Fixed strict mypy narrowing for dynamic annotation and scoring inputs.
- Declared optional-module mypy overrides for spaCy and huggingface_hub.
- Added setuptools and wheel to development dependencies for reproducible local builds.
- Excluded runtime `.log` files from public-package boundary scans.
- Made the security-scan CLI print its machine-readable report before fail-closed exit.
- Added a regression test for local full-reproduce logs containing absolute paths.

## 0.1.0 — 2026-08-04

- Initial publication-grade construction repository.
- Added source auditing, reconstruction, mining, privacy, blinding, annotation, adjudication, continuity, split, scoring, trajectory, claim, readiness, release, and clean-room modules.
- Added sample-derivative StudyChat audit and blocked full-data/release gates.

## 0.2.0 - Full-source private pipeline repair

- Added executable `full-*` Make targets using the external `MGP_FULL_INPUTS` directory.
- Added full StudyChat reconstruction and duplicate-partition verification.
- Added complete WikiConv 2003/2018 streaming census and bounded lineage construction.
- Added privacy/blinding, offline AI-provisional replay, continuity, split, validation, readiness,
  and full claim-ledger targets.
- Fixed the reported Ruff violations, source-based mypy configuration, package typing marker, and
  artifact-build fallback behavior.
- Retained the earlier sample-derivative workflow under explicit legacy targets.

## 0.2.1 - 2026-08-04

- Fixed the six Ruff diagnostics encountered after a successful full-source run.
- Preserved full-source counts, candidate artifacts, privacy/blinding outputs, and component-disjoint splits.
- Bumped package version to 0.2.1.

