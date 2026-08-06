# Controller Run Failure Ledger, LongMemEval-M

Every important observed failure across the LongMemEval-M controller run family,
with originating run, log/file evidence (exact path), the responsible pipeline
layer, the correction applied (with fix-doc citation), regression evidence, and
the remaining limitation. Paths are absolute. Numbers were read from the cited
files for this audit.

Abbreviations: base run `V7 = ask_controller/runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v7`;
replay family under `LV = ask_controller/runs/lme_m last version`; canonical
source `SRC = ask-memory-governance/src/ask`.

> **Superseding status (ledger v1.1).** The historical `139/180 = 77.2%`
> artifact is `failure_replay_only`, selection-biased, and not a final result.
> The Modal top-up completed 84/110 carried-forward items, with 71 correct and
> 13 regressions. Together with the 70 replayed failures this gives 96/154 raw
> over observed items, full-180 raw bounds of 53.3–67.8%, and bounds of
> 55.6–70.0% if four Codex/GPT-5 overrides are retained.

---

## Ledger

### F1, HTTP 402 credit exhaustion converted to empty extraction fallbacks
- **Originating run:** V7 controller.
- **Evidence:** `V7/controller/extraction_trace.jsonl`, audit scan for this
  report: 11,505 traces total, **736** with an `error` field, **316** whose
  error string contains `402`, **388** empty extractions with zero model
  responses. `V7/ANALYSIS_REPORT.md` §5 ("≥315 calls recorded HTTP 402
  insufficient-credit failures … 388 unrecoverable empty fallbacks").
- **Responsible layer:** Extraction (`SRC/extraction/extractor.py`), via the
  provider transport (`SRC/inference/openai_compatible.py`).
- **Correction (V8):** `V8_FIXES_AND_RUN.md` change #6, "transient extraction
  failures are not cached." On a no-response, `Extractor.extract()` re-raises
  instead of writing a synthetic empty extraction
  (`extractor.py:145-162`); telemetry `extraction_uncached_failures`. Enabled by
  `--fail-on-extraction-error` (`run_vllm_cascade.py:208-216`).
- **Regression evidence:** `tests/test_extractor_recovery.py::`
  `test_extractor_propagates_failure_when_provider_returns_no_response`, the
  fake provider raises `RuntimeError("HTTP 402 insufficient credit")` and the
  test asserts `pytest.raises(RuntimeError, match="HTTP 402")`.
- **Remaining limitation:** V7's already-cached empties survive in
  `V7/controller/extraction_cache.jsonl`; the 110 retained-correct sessions in
  the v8 adjudicated merge were never re-run, so they still carry v7's
  contaminated state. A fully clean rerun with prepaid credit is still
  outstanding (ANALYSIS_REPORT §7 priority 1/6).

### F2, Extraction-empty caching bug (empties baked into the shared cache)
- **Originating run:** V7 controller/b4 (shared cache).
- **Evidence:** `V7/_shared_extraction_cache.jsonl` and
  `V7/controller/extraction_cache.jsonl`; ANALYSIS_REPORT §5 ("cached empties
  would silently survive resume … can change both memory state and answers").
- **Responsible layer:** Extraction caching (`orchestrator._append_extraction_cache`
  `orchestrator.py:1519`; `_merge_shared_extraction_cache`
  `run_vllm_cascade.py:375`).
- **Correction (V8):** never cache synthetic exception fallbacks; a real empty
  is cached only when a model actually responded
  (`extractor.py:145-200`, `empty_extraction_output` `:282`).
- **Regression evidence:** `tests/test_extractor_recovery.py::`
  `test_extractor_falls_back_to_empty_on_schema_echo` (empty allowed **with** a
  response) vs the F1 test (no response → raise). Content-keyed cache keys are
  exercised by `tests/test_extraction_concurrency.py`.
- **Remaining limitation:** cross-system seeding order (controller→b4→…) means a
  bad-but-responded extraction can still propagate; the cache is content-keyed,
  not correctness-keyed.

### F3, Thinking-mode token-budget failure (INVALID replay)
- **Originating run:** `LV/lme_m_modal_qwen35_9b_v8_failures` (INVALID).
- **Evidence:** `LV/lme_m_modal_qwen35_9b_v8_failures/INVALID.md`, "Qwen
  thinking mode was still enabled. Structured extraction calls repeatedly
  consumed the full 512-token budget without visible JSON, and strict v8
  extraction correctly aborted." Confirmed: 0 completed predictions across the
  10 shards (`controller/_shard*/predictions.jsonl` all empty).
- **Responsible layer:** Inference request config (chat-template kwargs) +
  extraction parse.
- **Correction:** send `chat_template_kwargs={"enable_thinking": false}` (the
  `--no-enable-thinking` default; `run_vllm_cascade.py:503`,
  `--openai-chat-template-kwargs-json`). Corrected config written to a new dir so
  no partial cache is reused.
- **Regression evidence:** the corrected rerun
  `LV/lme_m_modal_qwen35_9b_v8_failures_nothink/controller/predictions.jsonl`
  completed all **70** items (35.7% machine-correct). `extraction-max-new-tokens`
  default 512 rationale documented at `run_vllm_cascade.py:536-538`.
- **Remaining limitation:** the extraction abort is correct behaviour but means
  thinking-mode misconfiguration produces a total run loss, not a degraded run.

### F4, MiniLM signal-11 shard deaths (per-shard local embedder)
- **Originating run:** `LV/lme_m_modal_qwen35_9b_v8_failures` (first launch).
- **Evidence:** `INVALID.md`, "loaded one local MiniLM model per shard. All ten
  shards exited with signal 11 during concurrent native model initialization."
  (Cf. `V7_FIXES_AND_RUN.md` test note: 2 MiniLM smoke tests are "gated off for
  Apple-Silicon segfault safety".)
- **Responsible layer:** Embedder loading (`SRC/baselines/embeddings.py`; served
  variant `scripts/serve_embeddings.py`).
- **Correction:** run one **shared** MiniLM embedding server over HTTP and verify
  the served model identity, instead of loading the model in every shard
  (`run_vllm_cascade.py:104-116` embedder routing; `--embed-base-url`
  `:577`, `--embedder-device cpu` default `:585` with an explicit OOM rationale).
- **Regression evidence:** the `_nothink` corrected rerun used the shared server
  and completed 70/70. Embedding backend covered by `tests/test_embeddings.py`.
- **Remaining limitation:** environment-specific (native ST init under
  concurrency); no unit test reproduces signal 11 directly.

### F5, v5 run misnaming + abort (unusable)
- **Originating run:** `ask_controller/runs/lme_m_openrouter_qwen_gemma_minilm_100_129_seed0_v5`.
- **Evidence:** directory is named `..._100_129_...` but the only data file is
  `range_200_239.jsonl` (its first record is `single-session-preference`,
  `ultrachat_139656`) → **misnamed**. `controller/` holds only `_shard*/`
  directories with **no merged `report.json`**. `KeyboardInterrupt` appears in
  `v5/logs/main.log` and `v5/logs/controller_shard{2,11,12,14}.log` → aborted.
- **Responsible layer:** Run orchestration / operator (range/output naming +
  manual abort).
- **Correction:** superseded by v6 (200-239, 29/40=72.5%, complete) and v7
  (full strat30). v8 fixes add append-only logging + shard retries so aborts are
  recoverable (`run_vllm_cascade.py:258,280`).
- **Regression evidence:** none needed, the run is excluded; marked
  `aborted/unusable` in `artifacts/controller_run_comparison.json`.
- **Remaining limitation:** no automated guard prevents an output dir name from
  disagreeing with the slice range it contains.

### F6, Judge number-word / digit mismatch (false negatives)
- **Originating run:** V6 and V7 (systematic once the v7 prompt forced
  digit-form answers).
- **Evidence:** `VERIFY_v6_FAILURES.md`, session `89941a93` gold `4`, prediction
  `four`, "`[gold-token-guard] 1/1 gold tokens missing: ['4']` → correct=False
  (false negative)". V7 ANALYSIS_REPORT §2, `5c40ec5b` ("2" vs "twice"),
  `58ef2f1c` ("Valentine's Day" vs "February 14th") wrongly guard-rejected;
  overridden to correct.
- **Responsible layer:** Judge / grading guard (`SRC/eval/longmemeval.py`).
- **Correction (V7 §4-fix-2):** `_MULTIPLICATIVE_NUMBER_WORDS`
  (`once/twice/thrice→1/2/3`, `longmemeval.py:451`), `_collapse_number_words`
  (`:454`), thousands-separator collapse in `_normalize_text` (`:508-523`); the
  hard `[gold-token-guard]` reject now fires **only** on a provable numeric
  conflict, all lexical/date mismatches deferring to the LLM judge
  (`:734-755`).
- **Regression evidence:** `tests/test_v4_run_fixes.py::`
  `test_guard_subset_prediction_defers_to_judge`,
  `test_guard_defers_date_alias_to_semantic_judge`,
  `test_guard_still_rejects_numeric_mismatch_without_judge`;
  `tests/test_scaleup_500_m_fixes.py::test_normalize_text_collapses_thousands_separators`.
- **Remaining limitation:** the fix removed the false negatives but the residual
  guard still hard-rejects genuine numeric conflicts before the judge; some gold
  answers (e.g. `9a707b81` "21 days … 22 also acceptable") still needed manual
  adjudication because the guard cannot model gold-internal acceptance rules.

### F7, Aggregation scaffold removal (unvalidated hint)
- **Originating run:** V7 (scaffold enabled).
- **Evidence:** ANALYSIS_REPORT §3.3 / §7 and `V8_FIXES_AND_RUN.md` change #5 -
  "Replay on the 11 strat30 count/sum questions: scaffold enumeration matched
  gold 2/11, matched the final answer 1/11, no value, added latency."
- **Responsible layer:** Answer generation (`orchestrator._aggregation_scaffold`
  `orchestrator.py:2568`).
- **Correction:** v8 profile omits `--controller-aggregation-scaffold`; it is
  re-added **only** when v7 is explicitly reproduced with `--no-v8-fixes`
  (`run_vllm_cascade.py:203-207`).
- **Regression evidence:** the 11 count/sum questions are retained as a
  development regression set (ANALYSIS_REPORT §3.3, "not a test set"). Ordinal /
  computation replay covered by `tests/test_computation_replay.py`.
- **Remaining limitation:** aggregation/counting accuracy remains unsolved
  (near-miss counts 2-vs-3, 4-vs-5, 22-vs-23 persist); v8 removes the hint but
  does not add a working aggregator.

### F8, Escalation no-op (BIG_MODEL == FAST_MODEL) in v7
- **Originating run:** V7 controller.
- **Evidence:** `V7_FIXES_AND_RUN.md` run block sets
  `FAST_MODEL=qwen/qwen3.5-9b BIG_MODEL=qwen/qwen3.5-9b`. ANALYSIS_REPORT §3.3 -
  "the v7 escalate-on-Unknown retry was designed to re-ask a stronger model, but
  this run set `BIG_MODEL == FAST_MODEL`, so it re-asked the same 9B … 26
  retries, 7 rescues, 18 post-retry refusals."
- **Responsible layer:** Answer-retry escalation + cascade wiring
  (`run_vllm_cascade.py`; `orchestrator.answer_escalation_llm`).
- **Correction (V8 change #3):** a genuinely separate escalation model
  (`ANSWER_ESCALATION_MODEL=qwen/qwen3.5-35b-a3b` →
  `--answer-escalation-model` → `--answer-escalation-openai-model` →
  `answer_escalation_llm`; `run_vllm_cascade.py:183-191`). Relation-classifier
  cascade escalation is gated on `big_model != fast_model`
  (`run_vllm_cascade.py:217-221`).
- **Regression evidence:** `tests/test_cascade_escalation.py::`
  `test_no_escalation_classifier_means_no_cascade`,
  `test_cascade_escalates_decision_critical_relation`.
- **Remaining limitation:** the 35B escalation's benefit was not measured in a
  clean full run; the adjudicated 139/180 uses the **v7** (no-op-escalation)
  answers for the 110 retained sessions.

### F9, Relation-classifier no-response → semantic Keep (state corruption)
- **Originating run:** V7 controller.
- **Evidence:** ANALYSIS_REPORT §5, "Relation classification had the same
  semantic-corruption path: no-response stage failures were converted to
  `independent/unclear`, then cached and allowed the session to complete."
  Cached in `V7/controller/relation_cache.jsonl` / `relation_trace.jsonl`.
- **Responsible layer:** Relation classifier (`SRC/classifier/relation.py`).
- **Correction (V8 change #7):** `RelationClassifier.classify()` re-raises on a
  no-response so shard retry/resume obtains a real classification instead of
  caching a Keep; the conservative `independent/unclear` fallback applies only
  when a model actually responded (`relation.py:100-130,143-160`).
- **Regression evidence:** `tests/test_relation_classifier.py::`
  `test_relation_classifier_propagates_no_response_provider_failure`.
- **Remaining limitation:** as with F1/F2, v7's already-cached
  `independent/unclear` verdicts persist in the retained 110 sessions.

### F10, Aggregation/scoring scaffold + `results.md` title bug
- **Originating run:** V7 (report generation).
- **Evidence:** ANALYSIS_REPORT §2, a dataset-agnostic `results.md` title fix
  (was hard-coded "LongMemEval-S"); five verdicts overridden in shard-level
  `judgments.jsonl` and reports regenerated through
  `merge_run_shards → build_eval_report`. Originals preserved as
  `V7/controller/report.json.pre_adjudication.orig` (0.6=108/180) vs
  `report.json` (0.6111=110/180).
- **Responsible layer:** Scoring/report (`SRC/eval/longmemeval.py:904`
  `build_eval_report`; `SRC/eval/merge.py:57` `merge_run_shards`).
- **Correction:** three code fixes to `longmemeval.py` (multiplicative words;
  head-anchored abstention detection; dataset-agnostic title); reports rebuilt
  deterministically (n_bootstrap=1000, seed 0).
- **Regression evidence:** `tests/test_scoring.py`, `tests/test_longmemeval_eval.py`,
  `tests/test_merge_shards.py::test_merge_unions_grades_and_rebuilds_report` /
  `test_merge_dedups_overlapping_sessions`.
- **Remaining limitation:** the v7 overrides are manual and "do not yet have an
  executable adjudication manifest" (ANALYSIS_REPORT §4/§7).

### F11, Broken manifest `replay_run` path (non-runnable provenance)
- **Originating run:** v8 adjudicated artifact build.
- **Evidence:** `LV/lme_m_v8_failure_replay_adjudicated/manifest.json` and
  `summary.json` record
  `provenance.replay_run = "runs/lme_m_modal_qwen35_9b_v8_v7_failures_nothink"`
  and `replay_dataset =
  "runs/lme_m_modal_qwen35_9b_v8_v7_failures_nothink/v7_controller_failures.jsonl"`.
  Verified for this audit: **no such directory exists** (neither under `runs/`
  nor under `runs/lme_m last version/`). The real completed replay is
  `LV/lme_m_modal_qwen35_9b_v8_failures_nothink`. The invalid write-target name
  also appears in `lme_m_modal_qwen35_9b_v8_failures/INVALID.md`.
- **Responsible layer:** Artifact provenance recording
  (`build_v8_adjudicated_report.py:388-392`, `--replay-run` argument value).
- **Correction:** none applied in-repo (the number crunching used the correct
  directory at build time; only the recorded string is wrong).
- **Regression evidence:** none, this is a provenance/label defect. The
  arithmetic 139/180 construction is internally consistent (`report.json`
  overall 0.7722222), but the selection rule makes it scientifically
  ineligible and the independent top-up does not reproduce it.
- **Remaining limitation:** the manifest is not a runnable reproduction recipe as
  written; a consumer following the recorded path would hit a missing directory.

### F12, Single-session-preference remains unresolved
- **Originating run:** V7 → v8 replay.
- **Evidence:** V7 SSP accuracy 11/30 (0.3667) in `V7/controller/report.json`.
  The 70-item replay `LV/lme_m_modal_qwen35_9b_v8_failures_nothink/controller/report.json`
  shows the `single-session-preference` row `accuracy: 0.0, n: 19`, i.e.
  **0 of the 19 selected SSP failures were repaired in that replay.** The
  replay prompts differ from v7, so this cannot isolate answer-model effects.
  In the independent top-up, 8 of 29 resolved SSP items were correct and one
  item remained unresolved, making 9/30 the most favorable possible total.
- **Responsible layer:** Retrieval coverage + answer grounding for preference
  profiles (`orchestrator._session_diverse_answer_order` `:2339`,
  `PREFERENCE_SYSTEM_PROMPT` per-competency prompt).
- **Correction (attempted):** v7 added a per-competency preference-profile prompt
  (V7 §4-fix-1); v8 added session-diverse context (change #2). Neither moved the
  SSP number.
- **Regression evidence:** `adjudication_audit.csv` shows SSP replay rows
  (`06f04340`, `1c0ddc50`, `75832dbd`, `d24813b1`, …) all
  `machine_correct=False, adjudicated_correct=False` with rationales citing
  fabricated/off-rubric specifics (wrong ingredients, wrong domain).
- **Remaining limitation:** SSP is unresolved, it "combines both bottlenecks"
  (retrieval coverage + grounding), per ANALYSIS_REPORT §3.3. Neither the
  selected replay nor the independent top-up supports carrying forward the
  historical carry-forward artifact at 11/30. The independent top-up instead
  observes 8/29 with one unresolved item (maximum 9/30), so no SSP total is
  unchanged or transferable across configurations.

---

## Cross-cutting note on residual contamination

F1, F2, F9 share a root cause (provider no-response converted to semantic
state) and share a residual limitation: the v8 fail-closed fixes were verified by
unit tests but the **110 v7-correct sessions were never re-executed** under the
fixed pipeline. They are carried verbatim into both the 135 (raw) and 139
(adjudicated) merged figures. A frozen, prepaid, single-judge full rerun remains
the only way to retire this class (ANALYSIS_REPORT §6/§7).
