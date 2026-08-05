# Behavior → Code Traceability, LongMemEval-M Controller

Maps each observed behavior class from the LongMemEval-M runs to the responsible
code in the canonical repo (`ask-memory-governance/src/ask/...`) and the tests
(`ask-memory-governance/tests/...`) that cover it. All source line numbers were
read for this audit. Run-evidence paths are absolute and read-only.

Roots: `RUNS = external://Master/ask_controller/runs`,
`SRC = repo://src/ask`,
`TESTS = repo://tests`.

> **Superseding status (ledger v1.1).** References below to the 139/180 merge
> describe an ineligible, selection-biased `failure_replay_only` construction,
> not a final benchmark result. The later top-up observed 96/154 raw and implies
> full-180 bounds of 53.3–67.8% (55.6–70.0% with four Codex/GPT-5 overrides).

---

## 1. Extraction (turn → candidate memories)

| Behavior | Run evidence | Canonical module / function | Tests |
|---|---|---|---|
| Per-turn structured extraction (JSON schema, 512 tok) | `RUNS/…_v7/controller/extraction_trace.jsonl` (11,505 traces) | `SRC/extraction/extractor.py:118` `Extractor.extract`; `:202` `render_prompt`; schema `SRC/extraction/schema.py` | `TESTS/test_extraction_schema.py`, `test_extraction_conf0_kept.py` |
| Truncated-JSON salvage / recovery | v7 traces with `raw_validated_output` | `extractor.py:253` `_recover_output`; `:291` `_salvage_truncated_items`; `:357` `_postprocess_output` | `TESTS/test_extractor_recovery.py::test_extractor_salvages_complete_items_from_truncated_json`, `..._recovers_new_proper_possession_fact` |
| No-response → fail closed (not cached empty) | v7: 388 empty+no-response traces (§ Failure Ledger F1) | `extractor.py:145-162` (raise on empty `tracer.responses`) | `TESTS/test_extractor_recovery.py::test_extractor_propagates_failure_when_provider_returns_no_response` |
| Concurrent intra-question extraction | `V7_FIXES_AND_RUN.md` §5-fix-1 | `orchestrator.py:1361` `_extract_turns`, `:1399` `_extract_turn` | `TESTS/test_extraction_concurrency.py` |
| Content-keyed cache + repair regression | `…_v7/_shared_extraction_cache.jsonl` | `orchestrator.py:1502` `_extraction_key`, `:1519` `_append_extraction_cache` | `TESTS/test_extraction_repair_regression.py` |

## 2. Controller decision policy (Keep / Supersede / Abstain)

| Behavior | Run evidence | Canonical module / function | Tests |
|---|---|---|---|
| Three-action rule (S_abs/S_rev vs θ) | `…_v7/controller/action_log.jsonl` (Keep 12,358 / Supersede 402 / Abstain 790, per ANALYSIS_REPORT §3.1) | `SRC/controller/policy.py:39` `decide`; scores `SRC/controller/scoring.py`, `SRC/controller/score.py` | `TESTS/test_controller.py::test_action_rule_boundary_thresholds`, `::test_abstain_rule_boundary_thresholds`, `::test_m3w91_supersede_score_monotonicity` |
| Feature snapshot (c,e,f,r,rho) | action-log rationale strings | `SRC/controller/features.py`; `orchestrator.py:458` `feature_snapshot` | `TESTS/test_controller.py::test_feature_*` |
| Decision record / action log | `action_log.jsonl` | `SRC/audit/action_log.py`; `orchestrator.py:1907` `_write_decision` | `TESTS/test_action_log.py`, `test_actions.py`, `TESTS/test_controller.py::test_action_log_decision_roundtrip_via_pydantic` |
| Relation classification + cascade escalation | `…_v7/controller/relation_trace.jsonl` | `SRC/classifier/relation.py:70` `classify`; `orchestrator.py:1572` `_classify_relation`, `:1615` `_should_escalate` | `TESTS/test_relation_classifier.py`, `test_cascade_escalation.py` |
| Relation no-response → fail closed | ANALYSIS_REPORT §5 (v7 cached `independent/unclear`) | `relation.py:100-130,143-160` | `TESTS/test_relation_classifier.py::test_relation_classifier_propagates_no_response_provider_failure` |

## 3. Memory persistence

| Behavior | Run evidence | Canonical module / function | Tests |
|---|---|---|---|
| Insert active memory | `…_v7/controller/_shard*/` sqlite state | `SRC/memory/operations.py:34` `insert_active` | `TESTS/test_memory_operations.py::test_insert_n_items_active_count_equals_n_and_ids_monotonic` |
| Supersede + lineage link (prior→inactive) | Supersede 402× (action log) | `operations.py:76` `supersede`, `:234` `get_lineage` | `TESTS/test_supersede.py`, `test_memory_operations.py::test_supersede_flips_prior_inserts_replacement_and_writes_relation`, `::test_lineage_three_step_chain` |
| Atomic supersede / double-supersede raises |, | `operations.py:76,146` | `TESTS/test_memory_operations.py::test_supersede_is_atomic_under_forced_exception`, `::test_supersede_double_supersede_raises_loudly` |
| Evict (no lineage) |, | `operations.py:155` `supersede_evict` | `TESTS/test_memory_operations.py::test_supersede_evict_*` |
| Models / schema |, | `SRC/memory/models.py`, `SRC/memory/db.py` | `TESTS/test_schema.py` |

## 4. Retrieval / ranking

| Behavior | Run evidence | Canonical module / function | Tests |
|---|---|---|---|
| Active-only dense retrieval (excludes superseded) | `…_v7/controller/predictions.jsonl` `retrieval_session_ids` | `operations.py:199` `retrieve_active`; `orchestrator.py:1942` `_retrieve` | `TESTS/test_memory_operations.py::test_retrieve_active_excludes_superseded_even_when_more_relevant` |
| Query augmentation + ±2 neighbor expansion | ANALYSIS_REPORT §1 | `orchestrator.py:2171` `_augment_retrieval`, `:3125` `_expand_retrieval_neighbors` | `TESTS/test_pipeline_orchestrator.py` |
| Query-gated historical lineage (v8) | `V8_FIXES_AND_RUN.md` change #1; sneaker pair `07741c44` | `orchestrator.py:248` `_requests_historical_memory`, `:2025` `_historical_context_items` | `TESTS/test_pipeline_orchestrator.py`, `test_temporal.py` |
| Recency pruning (b3) discards mid-history | b3 SSA/SSP structural zeros (ANALYSIS_REPORT §3.4) | `SRC/baselines/recency_pruning.py` | `TESTS/test_recency_pruning.py` |
| Flat-vector raw-turn retrieval (b2) | b2 = 80/180 (`…_v7/b2/report.json`) | `SRC/baselines/flat_vector.py`, `flat_vector_store.py` | `TESTS/test_flat_vector.py`, `test_flat_vector_store.py` |
| Embedding backend (MiniLM/served) | F4 sig-11 shard deaths (INVALID.md) | `SRC/baselines/embeddings.py`; `scripts/serve_embeddings.py` | `TESTS/test_embeddings.py` |

## 5. Answer contract (context compilation → answer)

| Behavior | Run evidence | Canonical module / function | Tests |
|---|---|---|---|
| ~12k reranked, budget-trimmed context | 164/180 questions trimmed (ANALYSIS_REPORT §3.2) | `orchestrator.py:2327` `_rerank_for_answer`, `:2382` `_budget_trim_for_answer`, `:335` `_estimate_prompt_tokens` | `TESTS/test_prompt_budget.py::test_budget_trim_fits_keeps_floor_and_preserves_question`, `::test_answer_records_budget_extras` |
| Session-diverse ordering (v8 R6) | `V8_FIXES_AND_RUN.md` change #2 | `orchestrator.py:2339` `_session_diverse_answer_order` | `TESTS/test_prompt_budget.py`, `test_pipeline_orchestrator.py` |
| WORK→FINAL scaffold + FINAL parsing | `predictions.jsonl` answers | `orchestrator.py:258` `_extract_final_answer`; `:653` `answer` | `TESTS/test_v4_run_fixes.py::test_extract_final_answer_*` |
| Unknown-retry / escalation | 26 retries, 7 rescues (ANALYSIS_REPORT §3.3) | `orchestrator.py:3115` `_answer_needs_retry`; `answer_escalation_llm` | `TESTS/test_cascade_escalation.py` |
| Deterministic compute/ordinal/aggregation | count/sum failures (ANALYSIS_REPORT §3.3) | `orchestrator.py:2535` `_compute_answer`, `:2645` `_ordinal_list_evidence`, `:2568` `_aggregation_scaffold`; `SRC/controller/computation.py` | `TESTS/test_computation_replay.py`, `test_v4_run_fixes.py::test_implicit_sum_over_counted_set` |
| Degenerate-answer / conflict-block guards | session `852ce960` `$` truncation (docstring) | `orchestrator.py:2861` `_conflict_block`, `:2943` `_current_location_block`; `longmemeval.py:531` `looks_degenerate_answer` | `TESTS/test_v4_run_fixes.py::test_conflict_block_never_asserts_a_winner` |

## 6. Judge

| Behavior | Run evidence | Canonical module / function | Tests |
|---|---|---|---|
| Layered guards (blank/degenerate/refusal/abstention) | `…_v7/controller/judgments.jsonl` rationale tags | `SRC/eval/longmemeval.py:646` `LongMemEvalGrader.grade` (`:652,668,686,702`) | `TESTS/test_longmemeval_eval.py::test_grader_rejects_blank_non_abstention_without_calling_judge`, `::test_grader_rejects_non_abstention_refusal_without_calling_judge` |
| Head-anchored abstention-gold detection | `gpt4_59c863d7` misbucketing (ANALYSIS_REPORT §2) | `longmemeval.py:552` `_looks_like_abstention_gold` (first-40-char anchor) | `TESTS/test_longmemeval_eval.py::test_grader_accepts_unknown_for_longmemeval_abstention_gold`, `::test_grader_detects_abstention_from_gold_text_without_competency_label` |
| Number-word/digit + separator normalization | `89941a93` "four" vs "4" (VERIFY_v6_FAILURES.md) | `longmemeval.py:451` `_MULTIPLICATIVE_NUMBER_WORDS`, `:454` `_collapse_number_words`, `:508` `_normalize_text` | `TESTS/test_v4_run_fixes.py::test_guard_subset_prediction_defers_to_judge`, `test_scaleup_500_m_fixes.py::test_normalize_text_collapses_thousands_separators` |
| Numeric-conflict-only hard reject; else defer to LLM judge | v7 `[gold-token-guard]` rows | `longmemeval.py:718-755` (`numeric_conflict` gate) | `TESTS/test_v4_run_fixes.py::test_guard_still_rejects_numeric_mismatch_without_judge`, `::test_guard_defers_date_alias_to_semantic_judge` |
| Judge backend construction / caching | `judge_cache.jsonl` | `SRC/eval/judge.py:80` `build_judge_backend`; `:29` `JudgeBackendConfig` | `TESTS/test_judge_backend.py`, `test_rejudge.py` |

## 7. Scoring / aggregation

| Behavior | Run evidence | Canonical module / function | Tests |
|---|---|---|---|
| Per-competency accuracy + bootstrap CIs | every `report.json` `rows[]` | `SRC/eval/longmemeval.py:904` `build_eval_report`; `bootstrap_accuracy_ci` | `TESTS/test_scoring.py`, `test_longmemeval.py`, `test_longmemeval_eval.py` |
| Answerable/abstention decomposition | `report.json` `answerable_*`/`abstention_*` | `longmemeval.py:958-989` (`_is_abstention_grade`) | `TESTS/test_longmemeval_eval.py` |
| Shard union + dedup + rebuild | `…_v7/controller/report.json` (20 shards merged) | `SRC/eval/merge.py:57` `merge_run_shards`, `:34` `grade_from_dict` | `TESTS/test_merge_shards.py::test_merge_unions_grades_and_rebuilds_report`, `::test_merge_dedups_overlapping_sessions`, `::test_grade_from_dict_roundtrip` |
| Cascade driver logging / shard retry / redaction | `…_v7/logs/controller_shard*.log` | `scripts/run_vllm_cascade.py:246` `_command_for_log`, `:258` `_write_command_header`, `:280` `_run_logged_with_retries` | `TESTS/test_run_vllm_cascade_logging.py::test_command_headers_append_across_relaunches`, `::test_shard_runner_retries_called_process_errors`, `::test_command_for_log_redacts_*` |
| Adjudicated failure-replay merge | `LV/lme_m_v8_failure_replay_adjudicated/summary.json` | `scripts/build_v8_adjudicated_report.py:92` `adjudicate`, `:107` `grades_report`, `:285` `main` | (no dedicated unit test; guarded by internal asserts `:296-305`) |

---

## Coverage gaps

- **`build_v8_adjudicated_report.py`** has **no unit test** under `TESTS/`; its
  correctness rests on internal integrity assertions (base=180, replay=70,
  `failed_ids == replay ids`, overrides ⊆ replay). This is the script that
  produces the historical, ineligible 139/180 construction.
- **SSP grounding (F12)** has behavioral evidence
  (`adjudication_audit.csv`) but no code path that repairs it, the fix attempts
  (per-competency prompt, session-diverse context) are covered by tests, yet the
  selected replay repaired 0/19; independent top-up evidence leaves no stable
  full-dataset SSP score (8/29 resolved, one unresolved; maximum 9/30).
- The **MiniLM signal-11** environment failure (F4) has no reproducing unit test
  (native segfault under concurrency); MiniLM smoke tests are deliberately gated
  off (`V7_FIXES_AND_RUN.md`).
