# R4. Baseline overrides and the selection of the nine controller adjudications

Scripts were read as code with every string literal that is not an identifier, file name or field name masked (`scripts/r4_mask_script.py`), so no benchmark-derived note text was displayed or saved. Notes are characterised by length, equality and hash only. Labels: OBSERVATION, INFERENCE.

## A. Baseline verdict overrides (b1, b4)

Table: `BASELINE_OVERRIDES_TABLE.csv` (items) and `BASELINE_OVERRIDES_COUNTS.csv` (systems).

| System | Shard dir | Item id | Competency | Original | Overridden | Correct count before to after (system) | Correct count before to after (shard) |
|---|---|---|---|---|---|---|---|
| b1 | `b1/_shard5` | gpt4_59c863d7 | multi-session | correct | incorrect | 10 to 9 of 180 | 2 to 1 of 9 |
| b4 | `b4/_shard3` | 58ef2f1c | single-session-user | incorrect | correct | 112 to 114 of 180 (both items) | 5 to 6 of 9 |
| b4 | `b4/_shard5` | 5c40ec5b | knowledge-update | incorrect | correct | (same) | 6 to 7 of 9 |

OBSERVATIONS
- b2 and b3 have 0 overridden rows (80 and 43 correct before and after).
- Where the override fields appear: `judge_overridden`, `judge_original_correct`, `judge_original_rationale` occur only in `judgments.jsonl` of the merged baseline directory (`b1/`, `b4/`) and of the shard directories that hold the three items (`b1/_shard5`, `b4/_shard3`, `b4/_shard5`). The same rows also changed `correct`, `judge_score` and `judge_rationale`. The fields do not occur in `report.json`, `judge_cache.jsonl`, answers, predictions or any script in the run directory. The merged and shard rows are identical. The rows carry no `adjudicated` flag.
- Backups exist: `judgments.jsonl.pre_adjudication.orig`, `report.json.pre_adjudication.orig`, `results.md.pre_adjudication.orig` for all four baselines at top level, and `judgments.jsonl.pre_adjudication.orig` in the three shard directories. Comparing each backup with the current file reproduces the table exactly (b1: 1 row changed, b4: 2 rows, b2 and b3: 0 rows, same id sets). Backup hashes are in `BASELINE_OVERRIDES_COUNTS.csv` and in the `V12_RUN_FILE_INVENTORY.csv` of phase 15.
- `report.json` and `results.md` of the merged baseline directories were regenerated after the override (they show 9 and 114). The shard `report.json` files were not: they show 2 of 9 for `b1/_shard5` and 5 and 6 of 9 for `b4/_shard3` and `b4/_shard5`, equal to the counts before the override.
- All baseline files, including the backups, are byte-identical in `lme_final_controller_180_providerpool` (checked for judgments, report, results and the six backup files at top level plus the three shard backups). The overrides therefore predate the V12 controller run.
- The overridden rows have longer `judge_rationale` text (229 to 351 characters) than the other rows of the same system (b1: all 179 other rows have at most 59 characters; b4: 135 of the 178 other rows have at most 80 characters and 2 exceed 200, the longest being 214). The baseline judgment schema has 12 fields and no `judge_was_called` field, so whether a model call was made cannot be read from these rows.
- Documentation in the audit baseline commit (`f6bf66e4...`): `docs/audit/CONTROLLERRUN_FAILURE_LEDGER.md` item F10 (about the v7 tree) states that five verdicts were overridden in shard-level `judgments.jsonl`, reports regenerated through `merge_run_shards`, originals kept as `.pre_adjudication.orig`, and that the overrides are manual and "do not yet have an executable adjudication manifest". `reports/ERROR_TAXONOMY.md` item F10 repeats this and gives the controller change 108 to 110 of 180 for that tree. `docs/audit/RESULT_PROVENANCE.md` lists the v7 baseline counts as B4 114, B2 80, B3 43, B1 9, equal to the post-override counts here.
- No commit of the backup repository or of the audit baseline repository contains the string `judge_overridden` (history search over all refs in both repositories).

INFERENCE (not verified)
- The count of five overrides in F10 is consistent with 1 (b1) + 2 (b4) + 2 (the v7 controller, 108 to 110): 1 + 2 + 2 = 5. The ledger does not allocate the five overrides by system, so this allocation is an inference from counts.
- The earlier phase-15 statement that the override process is undocumented should be restated as: documented as manual, in place and without an executable manifest (F10); executable tool not located; reviewer, date and criteria not recorded.

Remaining questions for the owner: who or what produced the three overrides (a person, a script, or an assistant); on what criterion; whether b2 and b3 failures and b1 and b4 failures were reviewed with the same procedure and how many items were reviewed; and the date of the pass relative to the V12 controller run.

## B. How the nine controller adjudications were selected and applied

Files (SHA-256): `find_cases.py` `e80ff292...`, `adjudicate_nine.py` `7f8668a5...`, `adjudicate_controller_results.py` `0111a47c...`. Item table: `ADJUDICATION_NINE_TABLE.csv`.

### What the code does (OBSERVATION)

1. `find_cases.py` holds a dictionary `TARGETS` of nine item ids, each with a short written reason (20 to 91 characters). It scans a JSONL file (default `range_0_179.jsonl`, the evaluation slice) and writes `selected_cases.jsonl` and `selected_cases.json` containing the slice records whose text mentions one of the nine ids, printing a found or missing line per id. It contains no criterion that selects the ids: the ids are inputs. The output files are not present in the run directory.
2. `adjudicate_nine.py` holds a dictionary `ADJUDICATIONS` for the same nine ids with two-part notes (lengths 56 to 135 characters). For the judgments file given (default `controller/judgments.jsonl`) it writes a backup, sets `correct = true` and `judge_score = 1.0` for each listed id, keeps the earlier rationale as `judge_rationale_pre_adjudication` when it was non-empty, replaces `judge_rationale` by the note, and adds `adjudicated`, `adjudication_type = "manual"` and `adjudication_note`. Strict mode requires that each id is found exactly once and that exactly nine records change.
3. `adjudicate_controller_results.py` holds a third version of the dictionary (same nine ids). For every `judgments.jsonl` under a root (default `controller`, top level and the eight shard directories) it sets the same fields, records `correct_pre_adjudication = false` and `judge_score_pre_adjudication = 0.0` through `setdefault` without testing the stored value, adds `manual_adjudication_overrides_model_judgment`, rewrites matching `judge_cache.jsonl` entries (matched by equality of stored raw output or rationale), rebuilds `report.json` and `results.md` (10,000-resample unstratified percentile bootstrap, `numpy` generator seed 0, one generator shared across the overall interval and the competency rows) and writes `.pre_manual_adjudication.orig` backups once. It raises if any of the nine ids is not found under the root.

### Order of application (INFERENCE from stored data)

- The notes stored in all nine rows, at top level and in the shards, equal the notes of `adjudicate_controller_results.py`. The notes of `adjudicate_nine.py` equal them for 7 of 9 ids and differ for two (`gpt4_7a0daae1`, `06878be2`), so the note texts were revised between the two scripts.
- In the merged `controller/judgments.jsonl` the field `judge_rationale_pre_adjudication` of item `a82c026e` has the same length (131) and, within the script comparison, the same content as the `adjudicate_nine.py` note for that id, whereas the shard row and its `.orig` backup hold an empty string. This is what happens if `adjudicate_nine.py` ran on the merged file before the generic script (it stores a pre-adjudication rationale only when the old one is non-empty), and `adjudicate_controller_results.py` then read the already replaced rationale as the "previous" value. Consequence: for this id the merged file's pre-adjudication rationale is an earlier manual note, not the judge output. Verdict fields are unaffected.
- The shard rows do not show the nine-script rationale, so `adjudicate_nine.py` appears to have been applied to the merged file only; the generic script was applied to the merged file and all shards.

### Selection criteria and search procedure (what is documented and what is not)

- Documented: nine hard-coded ids with a preliminary reason each and a final note each; a script that retrieves slice records for those ids; scripts that apply a fixed upward override; backups of the model judgments (`judgments.jsonl.pre_manual_adjudication.orig`) in the seven shards that contain an adjudicated item (shards 0 to 5 and 7).
- Not documented in any file read: why these nine ids; how many of the 52 controller items judged incorrect before adjudication were reviewed; the review rubric; who reviewed; whether the reviewer saw baseline verdicts or answers; the dates; and whether any reviewed item was left unchanged. No reverse-direction (correct to incorrect) option exists in the code, and no log of rejected candidates exists.
- Counts (OBSERVATION): the controller had 128 of 180 correct before and 137 of 180 after. All nine changes are incorrect to correct. By competency (items judged incorrect before / adjudicated): single-session-preference 21 / 7, single-session-user 6 / 1, temporal-reasoning 12 / 1, multi-session 11 / 0, knowledge-update 1 / 0, single-session-assistant 1 / 0. Nine of 52 incorrect items (17.3 percent) were changed; 7 of the 21 incorrect preference items (33 percent).
- One adjudicated item (`gpt4_7a0daae1`, temporal-reasoning) has `judge_was_called = false`: its earlier verdict came from the deterministic guard, not from the model judge. It has no pre-adjudication raw output and no judge-cache entry, which is why 8 and not 9 judge-cache entries carry an adjudication marker. The comment in the script that the retained values are model produced does not hold for this item.
- The published description in `reports/RESULTS_LME_FINAL.md` (nine "semantic-equivalence" adjudications, each with a `.pre_adjudication.orig` backup of the machine judgment) is not fully matched by the files: the backup suffix is `.pre_manual_adjudication.orig`; no backup exists at top level; shard 6 has none because it has no adjudicated item; and the character of the nine adjudications cannot be classified without reading the free-text notes. Seven of the nine items are in the preference competency, where the reference is a rubric rather than a short answer.

### Applied to other systems? (OBSERVATION)

- The nine ids and notes were not applied to b1 to b4: no baseline file has `adjudicated`, `correct_pre_adjudication` or `.pre_manual_adjudication.orig`.
- Baseline verdicts on the nine ids: b1 0 correct, b2 2, b3 0, b4 5 (b4 correct on `0a34ad58`, `b0479f84`, `a89d7624`, `b6025781`, `gpt4_7a0daae1`; b2 correct on `a89d7624`, `b6025781`). For these five items the paired comparison with b4 moves from "b4 correct, controller incorrect" to "both correct" after adjudication.
- Baseline failures went through a different, separate pass (`.pre_adjudication.orig` backups for b1 to b4, three verdict changes, section A). The two passes differ in file naming, in recorded fields (`adjudicated` and `adjudication_note` versus `judge_overridden`), and in documentation. No evidence shows that the same reviewer, rubric or intensity of review applied to controller and baseline failures; the 43 controller items and 66 b4 items still judged incorrect have no recorded review.

### Effect on claims (bounded)

The reported 137 of 180 contains nine controller-only post-hoc upward verdict changes from a hard-coded list, with 128 of 180 as the unadjusted count (earlier phase: raw 128/180). This record does not show that the changes are wrong; it shows that the selection procedure is not reproducible from the files and was not applied to the comparators with the same documentation. Any comparison that uses 137 for the controller and 114 for b4 mixes a controller-only manual pass with a separate undocumented baseline pass.
