# Task R summary: V12 run reconciliation and provenance

Output directory: `ASK_CLAUDE_SCIENCE_AUDIT_20260927/p17_v12_reconciliation/`. Evidence: owner backup run `lme_final_controller_v12_qwen_180`, phase-15 record, repository derived manifest. Baseline commit `f6bf66e4766d769727edf6b42c76b9977b14978a`.

## Not done, and why (declared reductions)

- The slice file `range_0_179.jsonl` was not opened. The question-to-support-session mapping used in R1 comes from the shard progress logs; the 180 expected ids were checked against the manifest id hash (equal), not against the slice.
- No judgment, answer, prediction or cache text was printed or saved. Adjudication notes were not read (scripts were rendered with free-text strings masked). Exception messages in shard logs were not read; only exception class names were.
- The adjudication notes were therefore not classified by reason (for example numeric equivalence versus preference rubric).
- `ARCHIVE_COMMANDS_FOR_OWNER.sh` was written and syntax-checked with `bash -n` only; it was not executed.
- `_shared_extraction_cache.jsonl` was hashed through the phase-15 inventory only; it was not scanned.
- The tool that produced the three baseline overrides was searched for in the run directory, the backup repository (working tree outside `runs_local`, and history of all refs) and the baseline repository history; not found. Other locations on the machine were not searched.
- No scope was reduced by sampling, caps or time limits: all 12,654 action-log rows, all 8 shard logs, all 180 ids and all 17 code files were processed.
- Repository state: `git status --short` of `ASK-memory-governance` was recorded before and after (`repo_git_status_before.txt`, `repo_git_status_after.txt`): identical (2 modified files and 3 untracked files that were already present: the working tree differs from the baseline commit; nothing was changed by this work). The backup repository was accessed only with read-only git plumbing.

## Status per subtask

| Subtask | Status | Result | Exact remaining question |
|---|---|---|---|
| R1 surplus of 883 | RESOLVED | 883 of 883 allocated: 822 stale rows of 20 stopped partial question runs replayed after restart (exact prefix match, 822 of 822) plus 61 rows of repeated decisions on cached extraction outputs shared by questions of one shard; 0 unexplained. The two counts (12,654 and 11,771) are in different units; comparable-unit identity is 12,654 = 11,832 + 822 and 11,832 = 11,771 + 61 | None blocking. Minor: one trace row (shard 1) without a cache entry is not characterised; 16 of 43 repeated lookups are not visible at item level |
| R2 coverage | PARTIALLY RESOLVED | Result coverage is established: 180 of 180 ids in predictions, answers and judgments (0 missing, 0 duplicate, 0 unexpected), each from exactly one shard, matching the round-robin rule; hashes recorded. Operational metadata is incomplete: manifest `status` is `running`, `exit_code` 1 and `failed_at_utc` are values from invocation 2, with no completion record for invocation 3 | How was invocation 3 (2026-07-19T08:56:03Z) launched and how did its launcher process end (success path not recorded)? |
| R3 evaluated code manifest | RESOLVED for identity, reachability and diffs; archive step needs the owner | 17 of 17 hashes recovered and equal to the manifest. Ten blobs are unreferenced (all in one cruft pack, object time 2026-08-05T16:59:03Z), seven are reachable. Diffs against the baseline commit are written (orchestrator first, 912 normalised changed lines). The archive script is ready, not executed | (a) Owner runs or declines the archive script. (b) Why does the manifest use `src/ask/...` keys and `ask-memory-governance` paths when the evaluated launcher and `run_baseline.py` use `ksa`: post-run text normalisation or a compatibility layer? |
| R4 baseline overrides and adjudication selection | PARTIALLY RESOLVED | Three baseline overrides tabulated with counts (b1 10 to 9, b4 112 to 114), field locations, backups (`.pre_adjudication.orig`, all four baselines), and documentation (F10 of the failure ledger: manual, no executable manifest). The nine controller adjudications: code, order of application and defects documented; selection criteria are not recorded anywhere | Who or what made the three baseline overrides and on what criterion? How were the nine controller ids chosen, how many of the 52 failures were reviewed, and was any baseline failure reviewed by the same procedure? |

## Findings most relevant to the manuscript (OBSERVATION unless marked)

1. The merged `action_log.jsonl` contains 822 rows (6.5 percent) that belong to no completed question run. Action counts from the completing runs are Keep 10,712, Supersede 373, Abstain 747 (total 11,832).
2. "11,491 processed turns" counts extractor invocations; 11,477 distinct cache keys and 11,520 final-run turn lookups (180 x 64) exist.
3. Baseline overrides are documented in the baseline commit (F10, v7 tree) as manual, in place, without an executable manifest; backups exist; merged reports were regenerated after the override and shard reports were not.
4. The controller adjudications use a hard-coded list of nine ids; the merged judgments file carries, for one id (`a82c026e`), an earlier manual note in the pre-adjudication rationale field; one adjudicated item (`gpt4_7a0daae1`) came from the deterministic guard, not a model call; the repository text describing the backups does not match the file names.
5. The ten unreferenced evaluated blobs sit in a cruft pack and are not in the public repository clone. INFERENCE: they are at risk under default `git gc`.
6. File modification times of all 903 run files are one normalised value; they cannot date events.

## Files

- Deliverables: `SURPLUS_883_RECONCILIATION.md/.csv/.json`, `COVERAGE_AUDIT.md/.json`, `EVALUATED_CODE_MANIFEST.csv`, `EVALUATED_CODE_MANIFEST_NOTES.md`, `evaluated_vs_baseline_diffs/` (15 diffs and `INDEX.csv`), `ARCHIVE_COMMANDS_FOR_OWNER.sh`, `BASELINE_OVERRIDES_TABLE.csv`, `BASELINE_OVERRIDES_COUNTS.csv`, `ADJUDICATION_SELECTION_RECORD.md`, `ADJUDICATION_NINE_TABLE.csv`, `SUMMARY.md`, `SHA256SUMS.txt`.
- Row-level support: `SURPLUS_883_STALE_ROWS_822.csv`, `SURPLUS_883_REUSE_KEYS_61.csv`, `WORKER_PROCESS_TABLE.csv`, `COVERAGE_ID_TABLE.csv`.
- Scripts in `scripts/` (run order: `r1_parse_shard_logs.py`, `r1_process_table.py`, `r1_align_rows.py`, `r1_units.py`, `r1_worker_deaths.py`, `r1_build_outputs.py`, `r1_final_join.py`, `r1_group_classification.py`, `r1_final_tables.py`, `r2_coverage_audit.py`, `r3_blob_identity.py`, `r3_pack_membership.py`, `r3_build_manifest.py`, `r3_write_archive_script.py`, `r4_*.py`). Intermediate JSON in `handoff/` (ids and hashes only). Superseded or exploratory scripts are kept: `r1_join_probe.py`, `r1_join_probe2.py`, `r1_text_mismatch.py` (its matching logic was wrong and gave 85 unmatched rows; replaced by `r1_text_mismatch2.py`, which pairs the 23 session-field disagreements), `r1_trace_dups.py`, `schema_probe.py`, `log_skeleton.py`.
- Environment: standard-library Python 3 for all scripts; git 2.x plumbing read-only. Re-running `r1_*` and `r2_*` requires the backup run directory path as first argument.
