# R2. Coverage audit of the V12 controller run

Scope: `runs_local/lme_final_controller_v12_qwen_180/controller` (merged artifacts and 8 shard directories). Only ids, counts, booleans and hashes were read from answer, prediction and judgment files. Labels: OBSERVATION, INFERENCE.

## Established (result coverage)

1. **Expected ids.** The 180 expected question ids were reconstructed from the per-shard progress logs (one `done` line per question; slice position = shard + 8 x j for the j-th question of a shard). The SHA-256 of the newline-joined ids is `93ee0e5eac2d836856cd12c3dc02ae953735bab53d93d7c6698ff69bfd5de465`, equal to `evaluated_session_ids_sha256` in `manifest.json` and in the repository derived manifest. Ordered and sorted lists give the same hash, so the slice is ordered by id. OBSERVATION: the expected set is the manifest-attested set; the slice file itself was not opened.
2. **Presence in merged artifacts.**

| Merged artifact | Rows | Distinct ids | Duplicate ids | Expected ids missing | Unexpected ids | SHA-256 |
|---|---:|---:|---:|---:|---:|---|
| `controller/predictions.jsonl` | 180 | 180 | 0 | 0 | 0 | `b12f64f2e3b8b641c8a03b473bab3d3f8fff2a6f6bf94fb610eee9140ee11915` |
| `controller/answers.jsonl` | 180 | 180 | 0 | 0 | 0 | `b12f64f2e3b8b641c8a03b473bab3d3f8fff2a6f6bf94fb610eee9140ee11915` |
| `controller/judgments.jsonl` | 180 | 180 | 0 | 0 | 0 | `d2c6b00c261335dfdc23fe2945a42f111349c68ed7bc0f825dff8ed8c6e1beb1` |

   `predictions.jsonl` and `answers.jsonl` are byte-identical. `report.json` holds no per-question ids; its coverage is shown by `n_sessions` = 180, six competencies with n = 30 each (sum 180), answerable_n 171 plus abstention_n 9. SHA-256 of `report.json`: `9220e0a0d9142caa4ec7d5af2110c94beffa076cebfe2d38b08a8d06e84c266c`; of `results.md`: `e861956f03bb21a05dc6b9bd73afe9db236e00b45743cebf4b68d65a2cdb1da7`.
3. **Source shard of each id.** Each of the 180 ids occurs in exactly one shard's `judgments.jsonl` (multiplicity 1 for 180 of 180) and the shard equals the round-robin rule position mod 8 for all 180 ids. Shards 0 to 3 hold 23 ids each and shards 4 to 7 hold 22 ids each. `COVERAGE_ID_TABLE.csv` lists, per id, slice position, expected shard, presence and multiplicity in the three merged files and presence in the four baseline judgment files.
4. **Merged versus shard files.** `predictions.jsonl` and `answers.jsonl` equal the shard concatenation (parsed row equality, shard-major order). The merged files are in shard-major order, not slice order. `judgments.jsonl` differs from the shard concatenation in one row (item `a82c026e`, shard 4) in one field, `judge_rationale_pre_adjudication`: the shard file and its `.orig` backup hold an empty string, the merged file holds a 131-character text whose length equals the earlier-pass manual note of `adjudicate_nine.py` for that id (see `ADJUDICATION_SELECTION_RECORD.md`). Verdict fields are identical in all 180 rows.
5. **Resume did not duplicate result rows.** In every shard the answers, predictions and judgments files hold one row per assigned id with 0 duplicates, and the shard `report.json` has `n_sessions` equal to the shard size. This matches the evaluated resume code (`run_baseline.py`, `_load_resume_state` and the rewrite of answers, predictions and judgments from the validated resume state, which drops partial tails), and `merge_run_shards` would in any case keep one row per id for these three files.
6. **Other artifacts were not de-duplicated by resumes.** The merged `action_log.jsonl` keeps 822 rows of stopped partial question runs (R1). `extraction_trace.jsonl` keeps 13 no-response extractor rows. `llm_calls.jsonl` records calls of all worker processes. These are provenance and cost facts, not result coverage.
7. **Hash agreement with the repository derived manifest** (`artifacts/manifests/lme_v12_derived_manifest.json`): `controller/judgments.jsonl` `d2c6b00c...`, `controller/report.json` `9220e0a0...`, `controller/action_log.jsonl` `08ebd013...`, `b4/judgments.jsonl` `2e61898f...`, `b4/report.json` `f6f8c42d...` all equal the values computed here. The four baseline judgment files each hold the same 180 ids (b1 `52e530ae...`, b2 `9f61c91b...`, b3 `3a3d7dbe...`, b4 `2e61898f...`).

Other merged artifact hashes: `action_log.jsonl` `08ebd01376534dbab37f084cc9384ab53b400d950f045aef041af10eb9c3912c`; `extraction_cache.jsonl` `a3f473e5bde5507d45cefaced88b40050dfeebb5782616b2ce637e4216d99d49`; `extraction_trace.jsonl` `70bd0b7dbaba1a1b620213111c7566eb0cc48beff1340b1f8d35c46359e7f6d9`; `relation_cache.jsonl` `51e2f26b9b27834fa75f230e7d913047570da63c53ebc6f2ebb6c7156be6ede0`; `relation_trace.jsonl` `3b32f3d7fa64a713bcd11ea6579b26449ad9a52e301fd3e888ed690f5c67b95e`; `_shared_extraction_cache.jsonl` is byte-identical to `controller/extraction_cache.jsonl` (hash comparison from the phase-15 inventory); `judge_cache.jsonl` `2b657f15cd0acd63e978be45d2c8ad22c844162ed83891b06ed2206cb27ec5ea`.

## Shard timeline (OBSERVATION from shard logs and `main.log`)

| Invocation (manifest `attempts`) | Started (UTC) | Ended | What `main.log` records |
|---|---|---|---|
| 1 (resume false) | 2026-07-18T19:30:38Z | before 05:50:06Z on 07-19 | shard 3 done, then KeyboardInterrupt in the cascade driver |
| 2 (resume true) | 2026-07-19T05:50:06Z | 08:54:21Z (equals `failed_at_utc`) | shards 3, 4, 7, 6, 5, 0, 2 done; shard 1 failed after its retries (RuntimeError listing shard 1) |
| 3 (resume true) | 2026-07-19T08:56:03Z | after 09:34:47Z (last action-log row) | all 8 shards done, `merged 8 shards -> overall=71.1% (n=180)`, shared extraction cache appended with 11,477 entries, `done` |

Inside these invocations the shard logs show 36 worker processes that did work (8 ran to completion, 28 stopped with RuntimeError or KeyboardInterrupt and were restarted by a shard retry or a later invocation) and 8 that only skipped an already complete shard. The final worker of each shard started with this many questions already complete: shard 0 20 of 23, shard 1 22 of 23, shard 2 22 of 23, shard 3 12 of 23, shard 4 21 of 22, shard 5 19 of 22, shard 6 20 of 22, shard 7 21 of 22.

## Remaining incomplete (operational metadata)

| Field or fact | Recorded | Observed | Status |
|---|---|---|---|
| `status` | `running` | all 180 results present and merged | not finalized |
| `exit_code` | 1 | invocation 3 reached `done` in `main.log` | stale value from invocation 2 |
| `failed_at_utc` | 2026-07-19T08:54:21Z | equals the end of invocation 2 | stale value from invocation 2 |
| `completed_at_utc`, `accuracy_gate_*` | absent | the launcher success path writes them and removes `failed_at_utc` and `exit_code` | success path not recorded |
| Completion time | none | last action-log row 2026-07-19T09:34:47Z; all 903 files carry one normalised mtime (2026-07-19T12:38) | file metadata cannot date the end |
| `homogeneity_report.json` | `homogeneous: false`, one global error (stale launcher hash) | per-system errors empty | report exists; date unknown |
| Manifest keys and path fields | code hashes keyed `src/ask/...`; paths under `/Users/ali/.../ask-memory-governance` | the evaluated launcher (blob `81927017...`) hashes `src/ksa/...` paths and the evaluated `run_baseline.py` imports `ksa` | see R3: manifest and logs were text-normalised after the run, or a compatibility layer existed; not resolved |

INFERENCE: the launcher writes `status` = `running` at each invocation start, keeps `failed_at_utc` and `exit_code` from an earlier failure until its success path runs, and sets `status` = `failed` with a new timestamp in an EXIT trap on a non-zero exit. Because the manifest shows neither a success record nor a failure record for invocation 3, the launcher process of invocation 3 probably ended without running either block (for example, killed or detached), or invocation 3 was started by a path that did not go through this launcher. This is not verified.

The repository derived manifest already lists the status, the exit code and the multiple resumes as known anomalies and records `missing_expected_outputs: []`; this audit agrees with the last item for the controller and baseline result files.

## What is and is not established

- Established: the controller run holds a complete, duplicate-free, manifest-consistent set of 180 predictions, 180 judgments and one merged report, each id from exactly one shard, with hashes recorded above.
- Not established: that invocation 3 finished through the launcher success path; the wall-clock duration of the run; the identity of the process that stopped invocation 1; and the cause of each RuntimeError.
- Not a coverage defect but a provenance caveat: the baselines in `b1` to `b4` are byte-identical copies from the earlier providerpool run (earlier phase); only the controller was executed in this run.
