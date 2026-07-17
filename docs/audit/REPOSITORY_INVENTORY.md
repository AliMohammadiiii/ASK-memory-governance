# Repository and artifact inventory

Date: 2026-07-12. Verified by direct listing. Names in the original execution brief map to actual materials as follows.

## Supplied inputs → actual locations

| Expected (brief) | Actual | Status |
|---|---|---|
| `KSACodes(1).zip` | `Master/ksa_controller/` working tree (+ `exports_2026-07-11/ksa_controller_CODE_2026-07-11.zip`) | present under different name |
| `ControllerRun(1).zip` | `Master/ksa_controller/runs/` (7 top-level run dirs incl. `lme_m last version/` family) + `exports_2026-07-11/ksa_controller_CODE_AND_RESULTS_NO_LOGS_2026-07-11.zip` (1.3 GB) | present under different name |
| `baseline(1).zip` | baseline outputs inside v7 run (`b1..b4/`) and `artifacts/mgp6_v2/ref_5systems/` | present, unpacked |
| `mgp6_v2_COMPLETE_2026-07-11(1).zip` | `exports_2026-07-11/mgp6_v2_COMPLETE_2026-07-11.zip` + live `Master/mgp6_v2/` tree | present |
| `MGP6_annotation_complete_package(1).zip` | uploads + `Master/mgp6_v2/MGP6_annotation_complete_package.zip` | present |
| `deep-research-report(8)(7).md` | uploads `deep-research-report(8).md` | present (close variant) |
| `Pasted markdown(58).md` | pasted venue-criteria analysis (in-conversation) | present as pasted text |
| Master Execution Plan | in-conversation brief | present |

No expected input is missing in substance.

## Primary material map

| Location | Content | Role |
|---|---|---|
| `Master/ksa-memory-governance/` | canonical public repository (this repo): `src/ksa`, `tests/`, `benchmarks/mgp6/`, `configs/`, `prompts/`, `schema/`, docs, CI | **canonical** |
| `Master/ksa_controller/` | full historical implementation + all LongMemEval runs + fix-history docs | evidence archive (read-only) |
| `Master/mgp6_v2/` | MGP-6 v2 dataset, scorer, systems, external adapters, all MGP-6 runs, annotation | evidence archive (read-only) |
| `Master/exports_2026-07-11/` | immutable zips of code and code+results | cold archive |
| `Master/MGP6_LongMemEval_Final_Report_EN.md` | narrative final report | secondary source |
| `Master/memory_benchmarks/` | external benchmark/datasets catalog | reference |
| `Master/thesis_docs/`, `Master/thesis_reports/` | thesis materials | input to thesis workstream |
| `Master/_archive_20260707/` | pre-consolidation archive | cold archive |
| uploads `ksa-memory-governance.zip` | snapshot of canonical repo (2026-07-12 02:27) | superseded by live tree |

## Canonical-repo completeness check (2026-07-12)

Present: `src/ksa` package, `tests/` (fixtures + suites), `benchmarks/mgp6` (dataset 180 rows + scorer + annotations), `configs/`, `prompts/`, `schema/`, `.github/workflows`, community files, `docs/` (architecture, adapters, reproduce, limitations), `thesis/MASTERS_THESIS_KSA_MGP6.md`, manifests.
Added this session: `docs/audit/*` (this audit set), `docs/research/SINGLE_SESSION_PREFERENCE_*`, `artifacts/results_ledger.*`, `artifacts/controller_run_comparison.json`, `artifacts/single_session_preference_error_taxonomy.json`, `scripts/evaluation/`, `scripts/analysis/`, reports, paper, protocol files (see `MASTER_EXECUTION_STATUS.md`).

## Deliberately excluded from the canonical repo

LongMemEval data (license/redistribution), 1.3 GB results zip, historical run logs, `.env` (secret hygiene — a live `.env` exists at `Master/.env` and must be rotated, never committed), local databases, `__MACOSX`/`.DS_Store` junk.
