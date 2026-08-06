# Reproduce results

This page lists supported reproduction entry points. It does not promote a dated
run beyond the status assigned by the scientific source of truth.

## Offline repository verification

```bash
source .venv/bin/activate
make release-check
```

For a quick iteration loop, use `make check`.

## MGP-6 v2 diagnostic

Validate the canonical 180-item source:

```bash
make validate-data
```

Inspect the maintained runner and scorer without network access:

```bash
python scripts/run_mgp6.py --systems no_memory --limit 1 --dry-run
python benchmarks/mgp6/metrics_mgp6.py --help
```

MGP-6 v2 results are diagnostic. Conflict type alone predicts the gold action on
the held-out split, so these commands reproduce measurements on the released
generator, not a population capability estimate. See
`audit/SCIENTIFIC_SOURCE_OF_TRUTH.md`.

## MGP-6 v4.3 integration

Public train/dev validation and dry-run commands are documented in
`../configs/experiments/mgp6_v43/README.md` and
`benchmarks/mgp6/v4.3/README.md`. Hidden input is intentionally unavailable to
post-final successor development, and the runner rejects attempts to combine
that system with hidden input.

## LongMemEval

LongMemEval data is not redistributed. A valid run requires the recorded external
input, an authorized provider credential, and the exact commands in
`../FINAL_RUN_MATRIX.yaml`:

```bash
export LONGMEMEVAL_DATA="${PWD}/.private/longmemeval/longmemeval_m_full.jsonl"
bash scripts/evaluation/run_longmemeval_final.sh --smoke
```

Load `OPENROUTER_API_KEY` from the approved secret manager before the smoke run.

No final eligible LongMemEval result ships with this release. Historical runs
and failure replays remain diagnostic, incomplete, invalid, or externally
pending as classified in `audit/CLAIM_ELIGIBILITY.md`.

## Machine-readable sources

Use the ledgers and manifests under `../artifacts/` when regenerating tables.
Human-readable reports under `../reports/` are dated outputs; do not hand-edit a
number in a report without regenerating it from its machine-readable source.
