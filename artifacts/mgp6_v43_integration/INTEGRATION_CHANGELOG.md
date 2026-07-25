# MGP-6 v4.3 integration changelog

## 2026-07-25 — dry-run preflight

- Activated Serena for the repository and completed read-only discovery.
- Verified the outer handoff and nested release in an isolated temporary
  directory.
- Confirmed ZIP integrity, five internal release archives, readiness metadata,
  and zero failed release gates.
- Recorded a proposed repository path map.
- Stopped before release placement and implementation because pre-existing
  uncommitted changes overlap `.gitignore`, paper sources, and thesis sources.

No benchmark records, private files, code, configurations, test files, paper
sources, thesis sources, ignore rules, releases, or experiment outputs were
changed.

## 2026-07-25 — implemented public integration and protected private placement

- Added a narrow ignored private boundary at `.private/benchmarks/mgp6/v4.3/`.
- Extracted hidden inputs, hidden gold, final human gold, and audit assets only
  beneath that ignored boundary; no private content was added to Git paths.
- Installed public train/dev records, safe metadata, and immutable source
  provenance under `benchmarks/mgp6/mgp6_v4_3/`; placed only the verified public
  and source/builder archives under `releases/MGP6_v4.3.0/`.
- Added the public-only loader/evaluator, resumable runner, configuration
  registry, development-only freeze index, documentation, and privacy tests.
- Updated the paper and authoritative ASK thesis with release facts and explicit
  pending-result placeholders; historical v2 results remain historical.

## 2026-07-25 — integration commit and CI confirmation

- Committed the selected public integration as
  `41f7ceeb38c971874b52578c4b622a704b992715`
  (`Integrate MGP-6 v4.3 final release`).
- Ran the complete local GitHub Actions-equivalent sequence after development
  dependencies were installed: repository validation, pytest, Ruff, Mypy, and
  package build all passed.
- Created `mgp6-v43-experiments` from that integration commit. Existing
  historical untracked material remains intentionally unmodified and untracked.

## 2026-07-25 — OpenRouter smoke-run hardening

- Committed `86e3674` (`Harden MGP-6 v4.3 OpenRouter smoke runner`) on
  `mgp6-v43-experiments`.
- Added runner support for OpenRouter reasoning control via
  `--reasoning-effort none`, raised the development default generation budget
  to 128 tokens, and separated transport retries from parse-format retries.
- Persisted raw invalid model responses and manifest counters before surfacing a
  parse failure, preserving public-only auditability without exposing private
  labels.
- Re-ran full local verification: `git diff --check`, Ruff, scoped Mypy,
  repository validation, full pytest, package build, and a deterministic runner
  smoke all passed.
- Confirmed a three-item public train OpenRouter/Qwen smoke with
  `--reasoning-effort none`: 3 predictions, 0 failures, 0 parse retries, 0
  invalid responses, and no hidden-gold access.
