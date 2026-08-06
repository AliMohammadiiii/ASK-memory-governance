# LongMemEval V12 provenance repair note

The original V12 manifest is preserved unchanged at
`runs_local/lme_final_controller_v12_qwen_180/manifest.json` and remains the
historical record of launcher state. It records three attempts, resume behavior,
`status=running`, `exit_code=1`, a failed timestamp, a dirty start, machine-local
paths, and code hashes that include a stale launcher hash.

`artifacts/manifests/lme_v12_derived_manifest.json` is a derived audit. It adds
current hashes for the stored action log, judgments, and reports and records the
known anomalies in a path-neutral form. It does not claim that the historical
run was cleanly finalized.

## Retrospectively verifiable

- Stored output bytes and their current SHA-256 values.
- The original manifest byte hash.
- The original configuration, model, judge, retry, resume, and dataset-hash
  fields that remain present in the historical manifest.
- Deterministic final-policy replay from the stored ASK-LME action log.
- Judgment counts and paired session alignment from preserved outputs.

## Not retrospectively repairable

- The stale launcher identity at execution time.
- A clean start-to-finish environment and dirty-tree digest.
- The missing historical finalization event.
- An uninterrupted full-run wall-clock duration.
- Gold semantic correctness for individual writes.

Therefore V12 can support bounded downstream and execution-replay claims, but
not a clean-room end-to-end reproduction or pristine provenance claim.
