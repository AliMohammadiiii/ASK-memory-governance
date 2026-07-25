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
