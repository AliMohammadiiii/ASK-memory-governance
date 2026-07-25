# Artifact Appendix

Availability, integrity, and redistribution status for the artifacts underlying
this paper. The authoritative manifests are
`artifacts/manifests/freeze_hashes.json` and
`artifacts/manifests/source_archives.json`. The release freeze is `final-1.1`.

## 1. What is released

| Artifact | Path | Released? |
|---|---|---|
| Controller + baselines + pipeline | `src/ask/` | Yes |
| MGP-6 scorer | `benchmarks/mgp6/metrics_mgp6.py` | Yes |
| LongMemEval scorer | `src/ask/eval/longmemeval.py` | Yes |
| Analysis scripts | `scripts/analysis/{audit_mgp6_validity,mcnemar_mgp6,build_final_results}.py` | Yes |
| MGP-6 v2 dataset (180 items) | `benchmarks/mgp6/data/mgp6_v2.jsonl` | Yes (checksummed) |
| MGP-6 per-item predictions | `artifacts/mgp6_v2/*/predictions.jsonl` | Yes, with coverage disclosed |
| Results ledger + generated tables | `artifacts/results_ledger.json`, `reports/FINAL_RESULTS.{md,json}` | Yes |
| Prompt templates | `prompts/` | Yes (checksummed by freeze manifest) |
| Test suite + CI | `tests/`, `.github/workflows/ci.yml` | Yes |

## 2. What is not redistributed

- **LongMemEval-M data** is external and not redistributed. Users supply the
  source dataset; the repository provides the stratification recipe (180 items,
  6×30, seed 0) and records source, slice, and ID-list hashes.
- **Provider transcripts or raw files that could contain credentials or
  identifying local paths** are excluded from the public review package.

## 3. Frozen inputs (SHA-256, release `final-1.1`)

The authoritative manifest is generated from the current release tree. We do
not duplicate volatile code/configuration or ledger hashes here, because that
would create a second stale source of truth after a release edit. Stable
data/result digests used by this paper are:

| Input | SHA-256 |
|---|---|
| `benchmarks/mgp6/data/mgp6_v2.jsonl` | `870705e71170026fc2e75dcc5b275f9a99ca3cc5501f054c2ac0d1a013b4a583` |
| `artifacts/results/mgp6_few6_report.json` | `eed881c69185902b5c892c8f8c6b4ac3e045d081abfc44f9e9eb8a9649f8aeaa` |
| external LongMemEval-M full source (not redistributed) | `89a0745fba506c37407da74f004515ba8a337a2aadc9ba9ba543030483223942` |
| external 180-item stratified slice (not redistributed) | `f10b4fb4173d3e2d9310d90c2b6bf8f5e7b147cea1d04affa9037b1b9fe6787d` |

## 4. Results-ledger integrity

- Ledger version `1.1`, created 2026-07-13.
- The ledger is the run-provenance source; scientific interpretation is
  superseded by `artifacts/analysis/mgp6_validity_audit.json` where the later
  construct-validity gate changes claim eligibility.
- MGP-6 v2 rows previously labelled `final_candidate` are diagnostic after the
  shortcut audit: conflict type alone reaches 1.000 held-out accuracy.
- The six-shot MGP-6 row is `incomplete`; LongMemEval rows are
  `diagnostic_only`, `failure_replay_only`, `incomplete`, `invalid`, or
  `externally_pending` as applicable.

## 5. Source-archive checksums

The authoritative sizes and digests for supplied archives are in
`artifacts/manifests/source_archives.json`. They are inventory evidence, not
publication-result inputs, and are not duplicated here.

## 6. Known limitations and non-final artifacts

- The six-shot MGP-6 decision run has 174 predictions. Its regenerated report
  aligns six missing IDs to `INVALID`, giving coverage-aware 0.7833 accuracy and
  0.7692 macro-F1. It remains `incomplete` and is excluded from final tables.
- The v8 LongMemEval 77.2% construction is `failure_replay_only` and contradicted
  by a non-empty top-up (96/154 raw observed; 53.3--67.8% full-slice bounds).
- A historical v8 adjudication manifest contains a non-runnable replay path and
  must not be used as the homogeneous recipe.
- The homogeneous `final-1.1` run is `externally_pending`: a smoke test stopped
  before inference on OpenRouter HTTP 403.
- Two forgetting-rate metrics saturate at 1.0 and are excluded from all tables.
