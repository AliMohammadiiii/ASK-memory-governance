# R3. Evaluated code manifest: notes

Companion to `EVALUATED_CODE_MANIFEST.csv` (17 rows), `evaluated_vs_baseline_diffs/` (15 diffs and `INDEX.csv`) and `ARCHIVE_COMMANDS_FOR_OWNER.sh` (not executed). Git was used read-only on the backup repository (`.../Documents_Backup_2026-09-26/.../ksa-memory-governance`) and on the audit baseline repository (`ASK-memory-governance`, commit `f6bf66e4...`); `git status --short` of the baseline repository was recorded before and after the work (see `SUMMARY.md`).

## Method
1. The 17 SHA-256 values were taken from `manifest.json` (`code_and_protocol_sha256`) and compared with `historical_code_and_protocol_sha256` in the repository derived manifest (17 of 17 equal).
2. Every blob of the backup object store (3,079 blobs among 4,636 objects) was streamed through `git cat-file --batch` and hashed. Each of the 17 values matched exactly one blob id. The copies in `phase15_v12_raw_evidence/recovered_evaluated_code/` were re-hashed and equal the manifest values (17 of 17).
3. Reachability was computed with `git rev-list --objects` for `--all` (all refs, including `refs/stash` and two `refs/codex/turn-diffs` tree refs), and separately for branches, remotes, tags, the stash, the codex tree refs, `HEAD` and `--reflog`. Commits that add or remove each blob were listed with `git log --all --find-object`, and commits that contain the blob at its path with `git log --all -- path` plus `rev-parse`.
4. Storage form was read from the pack indexes; object times for the cruft pack from its `.mtimes` file.
5. Each blob was compared with the baseline-commit file of the same path, and with the tree of the run's recorded `git_head` (`a284b2ef...`, commit date 2026-07-17T12:40:00+03:30). Diffs use `git diff --no-index --minimal -U3`, direction evaluated (minus) to baseline (plus). Normalisation for the changed-line count: `ksa` to `ask` (three letter cases), CRLF to LF, trailing whitespace stripped; count = deleted + added lines.

## Table (short form; full columns in the CSV)

| Logical file | Blob | rev-list --objects --all | Pack | Baseline-commit file of the same path |
|---|---|---|---|---|
| `FINAL_ANALYSIS_PLAN.md` | `43937b0786` | unreferenced | 7b7b92dd856f(cruft) | absent at same path (raw 20, normalised 10) |
| `FINAL_EVALUATION_PROTOCOL.md` | `140c68726b` | unreferenced | 7b7b92dd856f(cruft) | absent at same path (raw 22, normalised 6) |
| `FINAL_METRIC_DEFINITIONS.md` | `5aa2245509` | unreferenced | 7b7b92dd856f(cruft) | absent at same path (raw 26, normalised 22) |
| `FINAL_RUN_MATRIX.yaml` | `e7a65e9073` | unreferenced | 7b7b92dd856f(cruft) | absent at same path (raw 2, normalised 0) |
| `configs/models/openrouter_qwen_gemma.yaml` | `0c73435fa5` | reachable | f576fef2d255 | identical |
| `deploy/run_colab_modal_range.sh` | `c55ec8d1e7` | reachable | f576fef2d255 | differs (raw 4, normalised 4) |
| `scripts/analysis/check_controller_accuracy_gate.py` | `61c484c6da` | reachable | f576fef2d255 | identical |
| `scripts/evaluation/run_longmemeval_final.sh` | `819270176c` | unreferenced | 7b7b92dd856f(cruft) | differs (raw 40, normalised 26) |
| `scripts/run_baseline.py` | `870b1556b7` | unreferenced | 7b7b92dd856f(cruft) | differs (raw 65, normalised 25) |
| `scripts/run_vllm_cascade.py` | `dfc9530335` | unreferenced | 7b7b92dd856f(cruft) | differs (raw 21, normalised 17) |
| `scripts/verify_homogeneous_run.py` | `4ab53dbaca` | reachable | f576fef2d255 | differs (raw 2, normalised 2) |
| `src/ask/baselines/embeddings.py` | `b729d7deb8` | unreferenced | 7b7b92dd856f(cruft) | differs (raw 145, normalised 139) |
| `src/ask/controller/computation.py` | `6999a2dc0d` | reachable | f576fef2d255 | differs (raw 129, normalised 129) |
| `src/ask/eval/longmemeval.py` | `168d63ae55` | unreferenced | 7b7b92dd856f(cruft) | differs (raw 24, normalised 16) |
| `src/ask/eval/merge.py` | `bfee2a1253` | reachable | f576fef2d255 | differs (raw 12, normalised 12) |
| `src/ask/inference/openai_compatible.py` | `5da428a5fb` | reachable | f576fef2d255 | differs (raw 298, normalised 298) |
| `src/ask/pipeline/orchestrator.py` | `9b316b1f42` | unreferenced | 7b7b92dd856f(cruft) | differs (raw 914, normalised 912) |

## Findings (OBSERVATIONS)
- **17 of 17 evaluated files are recoverable and hash-identical to the manifest.** Seven are reachable from refs (the only commit that holds each of these blobs at its path is `ca0febce...`, tag `pre-mgp6-v43-integration`, dated 2026-07-25, which is after the run of 2026-07-18 to 19). Ten are not reachable from any ref, branch, tag, the stash, the codex tree refs or the reflog: `FINAL_ANALYSIS_PLAN.md`, `FINAL_EVALUATION_PROTOCOL.md`, `FINAL_METRIC_DEFINITIONS.md`, `FINAL_RUN_MATRIX.yaml`, `scripts/evaluation/run_longmemeval_final.sh`, `scripts/run_baseline.py`, `scripts/run_vllm_cascade.py`, `src/ask/baselines/embeddings.py`, `src/ask/eval/longmemeval.py`, `src/ask/pipeline/orchestrator.py`.
- **The ten unreferenced blobs are all in a cruft pack** (`pack-7b7b92dd...`, 1,012 objects, with an `.mtimes` file) with a recorded object time of 2026-08-05T16:59:03Z. The seven reachable blobs are in the regular pack `pack-f576fef2...`. The ten blobs are absent from the object database of the public repository clone; the seven reachable ones are present there.
- INFERENCE (default git behaviour, not tested here): objects in a cruft pack older than the cruft expiry (default two weeks) are deleted by the next garbage collection that rewrites the cruft pack. The recorded time is 52 days before the backup date (2026-09-26). The repository has no local `gc` or `cruft` setting. Preserving the ten blobs before any maintenance on that clone is advisable; the script prepared for the owner does this without rewriting history.
- **Relation to the run's recorded `git_head` (`a284b2ef`)**: 1 file identical (`src/ksa/eval/merge.py`), 1 absent (`scripts/analysis/check_controller_accuracy_gate.py`), 15 differ. This agrees with `git_dirty_at_start: true`. At that commit the package directory is `src/ksa`, and the four protocol documents sit at the repository root.
- **Relation to the baseline commit `f6bf66e4`**: 2 identical (`configs/models/openrouter_qwen_gemma.yaml`, `scripts/analysis/check_controller_accuracy_gate.py`); 11 differ at the same path (normalised changed lines: orchestrator 912, openai_compatible 298, embeddings 139, computation 129, run_longmemeval_final.sh 26, run_baseline.py 25, run_vllm_cascade.py 17, longmemeval.py 16, merge.py 12, run_colab_modal_range.sh 4, verify_homogeneous_run.py 2); 4 are absent at the same path because the baseline commit keeps the protocol documents under `docs/evaluation/` (compared there: plan 10, protocol 6, metric definitions 22, run matrix 0 normalised changed lines; the run matrix differs in 2 raw lines that vanish under the normalisation rules: package name, line endings or trailing whitespace). The orchestrator diff is `evaluated_vs_baseline_diffs/01_*`; the evaluated file has 4,301 lines and the baseline file 4,471.
- Equality of the 17 hashes shows what was hashed at launch. It does not show that the controller policy, scoring and feature modules (not among the 17) were identical to the baseline-commit modules, and it does not show behavioural equivalence between the evaluated runtime and the baseline-commit runtime; the diffs are the evidence for review.

## Naming discrepancy (OBSERVATION, unresolved)
The evaluated launcher (`run_longmemeval_final.sh`, blob `81927017...`) builds the hashed-file list with `src/ksa/...` paths and the evaluated `run_baseline.py` imports from the package `ksa` (20 import lines), yet `manifest.json` carries the keys `src/ask/...` and the shard logs show paths under `ask-memory-governance/src/ask/...`; the backup repository directory is named `ksa-memory-governance`. A launcher run would write `src/ksa/...` keys. Two explanations fit and neither is tested: the manifest and logs were text-normalised after the run (a rename of `ksa` to `ask` and a path rewrite to `/Users/ali/...`), or the working tree exposed both package names. The content hashes are unaffected; the logical file names in the manifest are labels. The manifest hash in the derived manifest (`1c531508...`, derived 2026-08-02) is for the normalised file, so any normalisation predates that date.

## Archive script
`ARCHIVE_COMMANDS_FOR_OWNER.sh` targets the backup repository only. It verifies the ten blobs, writes them to a new read-only directory outside any repository with `SHA256SUMS`, and contains an optional, commented block that creates a tree, one parentless commit object and one annotated tag so the blobs become reachable without moving any ref or rewriting history. It was checked with `bash -n` and was not executed.
