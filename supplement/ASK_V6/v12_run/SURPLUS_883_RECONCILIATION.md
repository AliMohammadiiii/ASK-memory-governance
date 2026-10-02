# R1. Reconciliation of the 883-row surplus (12,654 action-log rows versus 11,771 extracted items)

Run: `lme_final_controller_v12_qwen_180` (owner backup). Evidence handled as ids, counts and hashes only. The 950 MB slice file was not opened. Status labels: OBSERVATION (read from files), INFERENCE (derived), ASSUMPTION (stated).

## Result

**883 of 883 allocated (822 + 61); 0 of 883 unexplained, under assumptions A1 to A6 below.** The allocation is a partition of the 12,654 rows, not an average or a fit.

The earlier statement "883 = 12,654 - 11,771" holds arithmetically but compares two different units, so it should not be read as "883 duplicate decisions of unknown origin". In comparable units:

| Quantity | Unit | Value | Source |
|---|---|---:|---|
| Action-log rows | one candidate decision event, appended by any worker process | 12,654 | `controller/action_log.jsonl`, SHA-256 `08ebd013...`; equals the concatenation of the 8 shard logs (checked byte-wise by hash) |
| Cache items | validated extracted item inside one extraction-cache entry (one entry per distinct turn-extraction cache key) | 11,771 | 11,477 cache entries; equals the item sum over 11,491 extraction-trace rows because the 14 trace rows without a cache entry hold no items |
| Extraction-trace rows | one extractor invocation (includes 13 invocations with no model response) | 11,491 | `controller/extraction_trace.jsonl` |
| Turn lookups in the 180 completing question runs | cache lookups (hit or miss) logged at question end | 11,520 | 180 questions x 64 turns each (`done; ... extraction_cache=h/n` lines) |
| Rows written by the worker that completed each question | decisions in the 180 completing question runs | 11,832 | alignment below |
| Rows left by workers that stopped mid-question | decisions in 20 stopped partial question runs | 822 | alignment below |

Identity in comparable units: 12,654 = 11,832 + 822, and 11,832 = 11,771 + 61.

The figure "11,491 processed turns" is the number of extractor invocations (trace rows). Of these, 13 returned no model response and left no cache entry; 11,477 distinct cache keys exist; 11,034 distinct (support session, turn index, turn content) triples exist because the same turn text is extracted again under a different cache key in a different question (444 triples occur in more than one shard). The figure is therefore not a count of distinct turns.

## Mechanism table

| Mechanism | Rows explained | Distinct support sessions | Distinct questions | Worker stops | Evidence | Confidence |
|---|---:|---:|---:|---:|---|---|
| M1. Stale partial-question rows. A worker stopped while a question was in flight; the action log is opened in append mode on resume, the restarted worker re-ran that question from the start and wrote all of its rows again | 822 | 260 | 18 | 20 | Section "Method"; each of the 20 stale groups equals, in order, the leading rows of the same question as re-run by the completing worker (822 of 822 rows); all stale timestamps precede the completing rows | high (row level, exact) |
| M1a. Worker ended with RuntimeError and the cascade restarted that shard inside the same invocation (shard retry) | 365 | 126 | 12 | 12 | shard log: Traceback class name, then `[vllm-cascade] attempt k failed ... retrying` | high for counts |
| M1b. Worker ended with RuntimeError after the retry budget (2 retries) was used; the shard was re-run in a later invocation | 347 | 109 | 5 | 5 | shard log: Traceback class name, no retry marker, shard reported failed in `main.log` | high for counts |
| M1c. Worker interrupted (KeyboardInterrupt) and re-run in a later invocation | 110 | 34 | 3 | 3 | shard log `KeyboardInterrupt`; `main.log` attempt 1 ends with KeyboardInterrupt | high for counts |
| M2. Repeated decisions on one cached extraction output: the same turn extraction (same cache key) used by two or more questions of the same shard | 61 | 22 | 38 | | Per-shard join on (candidate text hash, type): 61 rows of positive excess, 0 of negative excess; each excess key is decided by at least 2 questions of one shard; count identity 11,520 lookups - 11,477 cache entries = 43 repeated lookups | high for the count (remainder of an exact partition); medium-high for the mechanism (27 of the 43 repeated lookups can be tied to items at item level; the other 16 are not visible, which is consistent with turns whose extraction holds no item) |
| Unexplained | 0 | | | | | |
| **Total** | **883** | | | | 12,654 - 11,771 = 883 = 822 + 61 | |

Sub-rows M1a to M1c sum to 822 rows and 20 stops. Their distinct-session counts sum to 269, above 260, because one support session can occur in stale groups of more than one cause.

By invocation recorded in `manifest.json` (attempt 1 started 2026-07-18T19:30:38Z, attempt 2 2026-07-19T05:50:06Z, attempt 3 2026-07-19T08:56:03Z), assigning each stale group to the invocation containing its last stale row: attempt 1 holds 696 rows (15 groups), attempt 2 holds 92 rows (4 groups), attempt 3 holds 34 rows (1 group). The two manifest-level resumes therefore account for 126 stale rows in 5 stops; the remaining 696 rows come from stops inside the original invocation.

Mechanisms considered and their contribution to the 883:

| Candidate mechanism | Contribution | Note |
|---|---:|---|
| Exact duplicate candidate ids within a session | part of M1 | 75 of the 88 repeated (session, candidate_id) pairs are a stale row and its replay: they come from the two stopped workers that were processing the opening question of their process (shard 1 worker 2, 56 rows; shard 4 worker 2, 19 rows), so the restarted worker, whose counter also starts at 1, reproduced the same ids. The other 13 pairs are two completing rows from different questions in different shards with coinciding counters; they are not surplus |
| Same text and type with regenerated ids | part of M1 and M2 | Of the 1,277 (session, text, type) groups with more than one decision: 722 consist only of a stale row and its replay; 391 are repeated across questions only; 86 are repeated inside one question only; 78 mix these causes (54 + 12 + 9 + 3 groups by combination, see JSON). Repetition across questions in different shards is not surplus: each shard extracts into its own cache, so the repeated rows are matched by separate cache items |
| Retries or resumed shards | 822 | M1 |
| Repeated extraction of the same turn | 0 of the 883 | 13 trace rows are extractor invocations with no response that were retried successfully; they carry no items and no decision rows. One further trace row without a cache entry (shard 1) is not characterised; it holds no item |
| Reprocessing of a session in more than one shard | 0 of the 883 | 285 support sessions are decided in at least 2 shards (1,932 completing rows); each shard has its own cache entries, so these rows are balanced item for item |
| Merge artifacts | enabling condition of M1 | `merge_run_shards` deduplicates `judgments`, `answers` and `predictions` by question id but concatenates `action_log.jsonl` without deduplication, so stale rows are carried into the merged log |
| Unexplained | 0 | |

Groups with different actions: 51 of the 1,277 groups contain different actions. None of them is a pure stale-and-replay group (0 of 722), consistent with deterministic replay of a question from cached extraction and relation outputs; all 51 involve repetition across questions or inside a question, where the memory state differs.

## Method (what was done)

1. Parsed the 8 shard logs (`logs/controller_shard{k}.log`) into worker-process segments using the `run_baseline` start line and the resume line (`completed=a/b`), recorded the exception class name or KeyboardInterrupt at each end, and the per-question lines (`start`, `ingest memory_session i/n <session id>`, `done`). 36 worker segments did work (8 ran to completion, 28 stopped abnormally: 25 RuntimeError, 3 KeyboardInterrupt) and 8 later segments only skipped an already complete shard. Eight of the 28 abnormal stops (one per shard, the very first worker, which had no completed question) had their rows removed by the next worker, which opened the log in write mode; the other 20 left the stale rows counted here.
2. Split each shard action log into worker epochs at candidate-counter resets (the counter restarts at 1 in a new process). The number of epochs equals the number of worker segments whose rows survive in the file in all 8 shards. A worker that starts with `completed=0` opens the action log in write mode and removes earlier rows; one that starts with `completed>0` appends (evaluated `run_baseline.py`: `append_action_log = resume and completed sessions`).
3. Aligned the rows of each epoch with the ordered `ingest memory_session` lines of that worker (runs of consecutive rows with the same support session id). All 12,654 rows were aligned; no run was left over in any epoch. This attaches a question id to every row.
4. Defined the completing worker of a question as the worker whose log holds that question's single `done` line (180 questions, 180 `done` lines, none repeated). Rows of the same question written by any other worker are stale.
5. Compared stale rows with the completing worker's rows of the same question by (support-session hash, text hash, type, action): the stale sequence equals the leading rows of the completing sequence in all 20 groups.
6. Joined completing-worker rows with cache items per shard on (text hash, type) to isolate the 61-row remainder.

Row-level outputs: `SURPLUS_883_STALE_ROWS_822.csv` (shard, row id, question id, worker, hashes), `SURPLUS_883_REUSE_KEYS_61.csv` (61 keys, question ids, session hashes), `WORKER_PROCESS_TABLE.csv`. Free text was never written; sessions and texts appear as 16-character SHA-256 prefixes.

## Assumptions

- A1. Each action-log row is one candidate processed once in one `answer()` call of one worker (read from `_process_session`, `_process_candidate` in the evaluated orchestrator, SHA-256 `e6ce596b...`).
- A2. A reset of `candidate_id` marks a new worker process (the counter is initialised to 1 in `__post_init__`). Verified by agreement between epoch count and the number of surviving worker segments in every shard.
- A3. Rows of one worker appear in the order of its ingest lines, and a session with no extractable item writes no row. Alignment consumed every run, which supports but does not prove the one-to-one assignment: a zero-row session immediately followed by a later ingest of the same session id would be assigned to the wrong event. The exact prefix match of all 20 stale groups makes a systematic error unlikely.
- A4. The question id printed in each progress line is the `session_id` of the evaluated item, and one `done` line marks completion of its decisions and retrieval.
- A5. The per-shard `extraction_cache.jsonl` files are the cache seen by each shard; the merged cache file is their concatenation (11,477 distinct keys equal 11,477 lines).
- A6. The question-to-support-session mapping was taken from the logs because the slice file was not opened.

## Effect on reported quantities (observations)

| Quantity | All 12,654 rows | 11,832 completing-worker rows | 822 stale rows |
|---|---:|---:|---:|
| Keep | 11,478 | 10,712 | 766 |
| Supersede | 397 | 373 | 24 |
| Abstain | 779 | 747 | 32 |

Any count taken from the merged `action_log.jsonl` (action mix, rows per type, rows per session) includes the stale rows. The R1 decision-rule replay (12,654 of 12,654 actions reproduced from logged features) remains valid as a statement about the rule applied to logged rows, because stale rows are themselves rule outputs; it does not select the completing-run rows. Per-call counts from `llm_calls.jsonl` also include calls made by stopped workers (rows of `llm_calls.jsonl` match the `[api-call:done]` lines of the whole shard log, for example 4,127 rows against 4,125 lines in shard 0).

## Residual items

- OPEN-minor: 11,491 trace rows, 11,478 with a response, versus 11,477 cache entries. Thirteen no-response rows are retried successfully (verified). The remaining one-row difference (shard 1) is not characterised. It affects no item count (trace and cache both hold 11,771 items).
- OBSERVATION: in 23 completing-worker rows the cache item's `evidence_span.session_id` differs from the session in which the candidate was ingested (same text and type; 24 cache items). The join above pairs them by text and type; the session-aware join reports them as 23 unmatched rows and 24 unmatched items that cancel. The field disagreement is not explained.
- OPEN: who stopped the original invocation (KeyboardInterrupt) and the cause of each RuntimeError are not recoverable from class names alone; messages were not read because they can contain model output.

## Recommendation (engineering, not a result)

Describe the merged log as "12,654 rows, of which 11,832 belong to completing question runs and 822 are replayed partial runs", or recompute action statistics from the 11,832 rows using `SURPLUS_883_STALE_ROWS_822.csv` as the exclusion list. Do not describe the 883 as duplicate extractions.
