# Repository modernization final report

## Executive result

The repository now passes its complete local offline release gate, both
manuscript builds, clean wheel installation, pre-commit hooks, prompt registry,
prose hygiene, document-path checks, claim verification, provenance checks, and
core dependency audit. The engineering result is a conditional local GO. The
publication decision remains NO-GO because external legal, human, venue, and
experimental gates are open.

## Baseline and verified problems

The baseline contained 897 Git entries and 1,096 regular tracked or non-ignored
files. The worktree already had 24 modified files plus substantial untracked
MGP-Natural work. The 17 GB directory footprint came from ignored local data,
not tracked source. One tracked LaTeX backup, an expanded 20 MB advisor handoff,
a stale 1.5 MB MGP-6 source ZIP, active fill-in tokens, 9 unregistered prompt
versions, mutable CI action tags, no pre-commit configuration, a public network
bind default, implicit remote-model code trust, and a failing thesis table were
confirmed.

The baseline offline gate passed with 599 tests and 14 skips. The paper built to
44 pages. The thesis failed at an unescaped table separator and stopped before
bibliography resolution.

## Target architecture and sources of truth

`src/ask/` remains the only installable package source. Benchmark contracts,
configuration, experiment records, prompt identity, machine evidence, human
reports, manuscripts, release policy, and historical records now have explicit
owners in `docs/architecture/REPOSITORY_ARCHITECTURE.md` and
`docs/architecture/SOURCE_OF_TRUTH.md`. The maintained tree is in
`docs/architecture/REPOSITORY_TREE.md`.

Reproducibility guidance is grouped under `docs/reproducibility/`. It includes
the quickstart, environment scope, result provenance, and generated-file
registry. `artifacts/`, `configs/`, `experiments/`, and `prompts/` now describe
their own authority and boundaries.

## Cleanup and migration

Seventeen source paths were migrated. Thirteen unreferenced converted thesis
support files and the LaTeX backup moved byte-identically to semantic historical
locations. Architecture, reproducibility, and administrative-field documents
were moved and rewritten. All old paths, destinations, old and new hashes,
reference updates, and validation methods are recorded in `MIGRATION_MAP.csv`.

No tracked research evidence was deleted. Exact tracked duplicates with distinct
scientific, packaging, or typing roles remain. The generated advisor handoff was
removed through a guarded reproducible cleaner. The stale benchmark ZIP, which
contained copied source, bytecode, `.DS_Store`, and macOS metadata, was moved to
the operating-system Trash and is recoverable. Another 55 MB of mypy, pytest,
and Ruff cache data was removed from the imported MGP-Natural workspace. Local
`tmp/` material was kept and ignored because it belongs to a separate proposal
workspace.

`FILE_DISPOSITION.csv` contains all 1,096 baseline regular files and no pending
decision. Final actions comprise 711 KEEP, 187 preserved user-owned inputs, 165
audit-evidence records, 13 identical archives, 11 ignored local files, 4
move-and-rewrite records, 4 distinct duplicate roles, and 1 generated duplicate
removal.

Candidate bytes fell from 19,980,390 to 16,342,380. Tracked regular-file bytes
remain effectively unchanged because evidence was moved rather than removed.
The total 17 GB working directory remains dominated by ignored local data.

## Code, packaging, automation, and security

The package metadata retains Python 3.11 and 3.12 support. Development tooling
now includes pinned pre-commit integration. CI uses full commit pins for
checkout and setup-python, tests both supported Python versions, separates
quality and research-contract jobs, and runs the full offline release gate.

Make targets now enforce prompt, prose, and document checks, final inventory,
pre-commit, manuscript builds, and guarded advisor cleanup. Thesis compilation
no longer regenerates chapters or unused converted support copies by default.
Markdown transfer is explicit.

The prompt registry covers all 9 templates with exact hashes and experiment
relations. Strong output-leakage and unfinished-content patterns are prohibited
in maintained prose. Common technical vocabulary remains an advisory density
measure because isolated words are not authorship evidence.

The embedding server now binds locally and remote code is opt-in. Hugging Face
loaders support immutable revisions. The maintained ML extra moved to an exact
Python 3.12 lock with Transformers 5.14.1, sentence-transformers 5.6.1, and
torch 2.13.0. The legacy external adapter environment has a separate exact lock
on Transformers 4.57.6. Live local checks covered direct generation, judging,
sentence embeddings, the loopback embedding service, the baseline runner, and
revision propagation. External adapter imports passed without paid,
private-data, or native-system execution. Full findings are in
`HUGGINGFACE_COMPATIBILITY.md` and `SECURITY_REVIEW.md`.

## Final validation

- Offline release gate: PASS, 610 tests and 14 documented skips.
- Ruff lint and format: PASS.
- Mypy supported scope: PASS.
- Package build, wheel inspection, and clean Python 3.12 install: PASS.
- Prompt, prose, and document-path validators: PASS.
- Pre-commit: PASS.
- Claim ledger: PASS, 26 claims and zero mismatches.
- Public/private boundary declaration: PASS; legal clearance false.
- Paper: PASS, 44 pages.
- Thesis: PASS, 157 pages, references resolved.
- Clean clone: PASS for `make setup`, `make release-check`, `make paper`, and
  `make thesis`; the clone remained clean after all builds.
- Core constraint vulnerability audit: PASS.
- Exact ML lock validation: PASS, including 68 targeted tests and 2 documented
  opt-in skips.
- Exact external-adapter lock validation: PASS for dependency consistency and
  adapter imports.
- Publication readiness: NO-GO, 16 recorded blockers.

Machine-readable results are in `FINAL_VALIDATION.json`. Scientific boundary
checks are in `SCIENTIFIC_INTEGRITY_CHECK.md`.

The first clean-clone thesis attempt exposed that the pinned
`thesis/template` submodule was present locally but was not initialized by the
documented setup path. `make setup` now initializes the pinned submodule, and
the complete sequence passed in a new no-local clone. The clean clone reported
605 passing tests and 19 documented skips because private or locally retained
evidence is deliberately absent; the full evidence-bearing workspace reported
610 passing tests and 14 skips.

## Decision

**CONDITIONAL GO for local software development, thesis review, and controlled
artifact review. NO-GO for public publication or release.**

The remaining conditions are external approvals and experiments, immutable
model-revision capture for new local runs, and native external-system evidence.
The pre-existing research work and modernization changes are separated into
thematic commits. Historical run records and environments were not rewritten.
No push was performed.
