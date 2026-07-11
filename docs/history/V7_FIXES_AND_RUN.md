# v7 fixes + 5-system stratified run

Implements every accuracy fix (§4) and efficiency change (§5) from
`ANALYSIS_200_239_v6.md`, verified against the real OpenRouter models
(`qwen/qwen3.5-9b` answerer, `google/gemma-4-31b-it` judge). All fixes are
opt-in flags that default to preserving prior behavior; the acceptance run
turns them on via `--v7-fixes` (on by default in the cascade).

Tests: **460 passed, 2 skipped** (the 2 skips are MiniLM smoke tests gated off
for Apple-Silicon segfault safety). Ruff clean.

## §4 — accuracy fixes

| # | Fix | Where |
|---|-----|-------|
| 1 | Per-competency **preference-profile** answer prompt for `single-session-preference` (gold answers are "The user would prefer …" profiles, not direct answers). Prompt tuned live against qwen+gemma. | `orchestrator.py` `PREFERENCE_SYSTEM_PROMPT`, `_effective_system_prompt`; flag `--per-competency-answer-prompt` |
| 2 | **Numeric normalization** — (a) answer prompt: write numbers in digits; (b) judge gold-token-guard: number-word↔digit (`four`↔`4`, `twenty-seven`↔`27`, `two hundred`↔`200`) so `four` vs `4` stops being a false negative. | `orchestrator.py` `DEFAULT_SYSTEM_PROMPT`; `longmemeval.py` `_collapse_number_words`, `_normalize_text` |
| 3 | **Escalate-on-Unknown** instead of re-sending an identical prompt — a commit-forcing retry system prompt, plus an optional stronger escalation model. | `orchestrator.py` `ANSWER_RETRY_SYSTEM_PROMPT`, `answer_escalation_llm`; flag `--answer-escalation-openai-model` |
| 4 | **Aggregation scaffold** for count/sum — model LISTS matching mentions as JSON, code dedups + counts/sums (arithmetic the 9B gets wrong). Validated live: sum 20+30+50=100 with the duplicate deduped; count=3 with the repeat deduped. | `orchestrator.py` `AGGREGATION_SCAFFOLD_PROMPT`, `_aggregation_scaffold`; flag `--controller-aggregation-scaffold` |
| 5 | **Verify computation bypass** — never blindly emit the deterministic result; also run the LLM and reconcile (keep the LLM answer on disagreement, e.g. the $120 vs $50 sum error), plus a confidence floor (0.9). | `orchestrator.py` `verify_computation_bypass`, `computation_bypass_min_confidence`, `_answers_equivalent` |
| 6 | **Ordinal list reconstruction** — reassemble an enumerated assistant list split across retrieval chunks before indexing item N. Validated: item 4 = "Delta" recovered from two chunks. | `orchestrator.py` `_ordinal_list_evidence`; `computation.py` `_solve_ordinal_list_item` (merge across evidence) |
| 7 | **Token-budget estimator** — was ~30 % under-counting dense JSON; now uses a real tokenizer (tiktoken) when available, else a char ratio × 1.4 safety factor. | `orchestrator.py` `_estimate_prompt_tokens`, `_load_token_encoder` |

## §5 — efficiency changes

| # | Change | Where |
|---|--------|-------|
| 1 | **Concurrent intra-question extraction** (independent per turn); the Keep/Supersede/Abstain decisions still run sequentially. Determinism proved by `tests/test_extraction_concurrency.py` and live (overlapping calls). | `orchestrator.py` `_extract_turns`, thread-safe `_extract_turn`; flag `--extraction-concurrency` (default 8) |
| 2 | **Lazy/targeted extraction** knob (`--controller-memory-top-k`, kept at 64 for recall; lower to 32 for the aggressive token save). | cascade `--controller-memory-top-k` |
| 3 | **Shared extraction cache** across runs/ranges/**systems** — content-keyed; controller's extractions seed b4/b3 (run order controller→b4→…). | `orchestrator.py` `shared_extraction_cache_path`; cascade `_merge_shared_extraction_cache` |
| 4 | **Answer-context cap + rerank** (~12k tokens, reranked by score). | `orchestrator.py` `answer_context_max_tokens`, `_rerank_for_answer` |
| 5 | **Shard guidance** — 20 shards per the run request (async extraction is now the wall-clock lever). | wrapper |
| 6 | **Embedder chunking** before the extraction prefilter so a long turn's tail isn't lost to the 256-token truncation. | `orchestrator.py` `prefilter_chunk_turns` |
| 7 | Relation stage kept as-is (100 % deterministic routing). | — |

## Run — all 5 systems, 30 per competency (6×30 = 180), 20 shards

Order: **controller → b4 → b3 → b2 → b1** (so the controller's cached
extractions seed b4/b3). Each system writes full per-question data
(`answers.jsonl`, `predictions.jsonl`, `judgments.jsonl`, `report.json`,
`results.md`, `llm_calls.jsonl`, `action_log.jsonl`, `extraction_trace.jsonl`)
under `runs/<OUT>/<system>/`, merged across the 20 shards.

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
bash deploy/run_lme_m_strat30_5systems.sh
```

That wrapper builds the stratified slice once
(`data/slices/longmemeval_m_strat30_seed0.jsonl`, deterministic under seed 0)
and runs the command below. To run it by hand instead:

```bash
JUDGE_OPENAI_EXTRA_BODY_JSON='{"provider":{"order":["wandb","venice"],"only":["wandb","venice"],"allow_fallbacks":true},"reasoning":{"enabled":false}}' \
OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
OPENAI_API_KEY_ENV=OPENROUTER_API_KEY \
OPENAI_EXTRA_BODY_JSON='{"provider":{"order":["venice","deepinfra","siliconflow"],"only":["venice","deepinfra","siliconflow"],"allow_fallbacks":true},"reasoning":{"enabled":false}}' \
FAST_MODEL=qwen/qwen3.5-9b BIG_MODEL=qwen/qwen3.5-9b JUDGE_MODEL=google/gemma-4-31b-it \
EXTRACTION_MAX_NEW_TOKENS=512 RELATION_MAX_NEW_TOKENS=256 OPENAI_MAX_MODEL_LEN=32768 \
RETRIEVAL_K=16 CONTROLLER_MEMORY_TOP_K=64 EXTRACTION_CONCURRENCY=8 \
ANSWER_CONTEXT_MAX_TOKENS=12000 V7_FIXES=1 \
OUT=runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v7 \
SLICE=data/slices/longmemeval_m_strat30_seed0.jsonl \
SAMPLE_FROM=0 SAMPLE_TO=179 \
SYSTEMS=controller,b4,b3,b2,b1 \
SHARDS=20 \
EMBED_MODEL_PATH=sentence-transformers/all-MiniLM-L6-v2 EMBED_MODEL_NAME=minilm \
EMBED_DEVICE=cpu EMBED_MAX_SEQ_LENGTH=256 EMBED_BATCH_SIZE=128 EMBED_CLIENT_BATCH_SIZE=128 \
bash deploy/run_colab_modal_range.sh
```

Prereq (build the stratified slice if running the raw command directly):

```bash
python3 scripts/build_stratified_slice.py \
  --src data/slices/longmemeval_m_full.jsonl \
  --out data/slices/longmemeval_m_strat30_seed0.jsonl \
  --per-competency 30 --seed 0
```

Set `V7_FIXES=0` to reproduce the pre-fix (v6) behavior for an A/B comparison.
