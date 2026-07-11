# v8 fixes + 5-system stratified rerun

Implements the prioritized interventions from the strat30 v7 analysis
(`runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v7/ANALYSIS_REPORT.md`,
recommendations R1/R2/R4/R6/R7 plus two trace-audit findings). All v8 behavior
is opt-in and layered over the v7 profile; `--no-v8-fixes` (or `V8_FIXES=0`)
reproduces the exact v7 path.

Tests: **425 passed, 5 skipped**. Ruff clean on every touched file.

## Accuracy / mechanism changes

| # | Change | Motivation (v7 evidence) | Where |
|---|--------|--------------------------|-------|
| 1 | **History-aware retrieval (R4).** Superseded lineage rows are retrieved through a separate top-k pool and injected tagged `[SUPERSEDED HISTORICAL VERSION]`, ONLY when the question explicitly requests a historical state (`initially/originally/previously/…` gate; bare "old"/"first" excluded). The lineage-handling instruction is appended to the system prompt (main + retry paths) only when the gate fires, so current-state prompts stay lineage-free and token-neutral. | Sneaker pair `07741c44`/`07741c45`: Supersede hid the historical value `retrieve_active` could no longer surface; controller forfeited the update-pair advantage. | `orchestrator.py` `_requests_historical_memory`, `_historical_context_items`, `HISTORY_LINEAGE_INSTRUCTION`; flags `--controller-history-aware-retrieval`, `--controller-history-retrieval-k` (v8: 4) |
| 2 | **Session-diverse answer context (R6).** Before the budget trim, ordering prioritizes cross-session coverage over repeated same-session chunks, capped per session. | 91% of prompts trimmed 228→100 items ranked by question-similarity only; single-topic floods evicted the one fact-bearing turn ("Whiskers vs Luna" class). | `orchestrator.py` `_session_diverse_answer_order`; flag `--answer-context-session-cap` (v8: 4, applied to controller AND b4 for a fair ablation) |
| 3 | **Real Unknown-retry escalation (R1).** The commit-forcing retry now runs on a genuinely stronger model. | v7 set `BIG_MODEL == FAST_MODEL`, so escalation was a no-op: 26 retries, 7 rescues, 18 post-retry refusals with evidence in context. | deploy: `ANSWER_ESCALATION_MODEL=qwen/qwen3.5-35b-a3b` → cascade `--answer-escalation-model` → `--answer-escalation-openai-model` → `answer_escalation_llm` |
| 4 | **Historical-question gating of the current-location block.** The deterministic "CURRENT LOCATION CANDIDATES" prompt block no longer fires on historical location questions. | Trace audit: historical "where did I initially keep…" questions were steered to the newest value by the block. | `orchestrator.py` `_current_location_block` (returns empty when `_requests_historical_memory`) |
| 5 | **v8 disables the aggregation scaffold.** | Replay on the 11 strat30 count/sum questions: scaffold enumeration matched gold 2/11, matched the final answer 1/11 — no value, added latency. Kept under v7 reproduction. | `run_vllm_cascade.py` (v8 profile omits `--controller-aggregation-scaffold`) |

## Integrity / robustness changes

| # | Change | Motivation | Where |
|---|--------|-----------|-------|
| 6 | **Transient extraction failures are not cached.** A provider no-response error propagates (trace records `error`, `responses: []`) instead of being cached as a valid empty extraction that permanently bakes an outage into the shared cache. Telemetry: `extraction_uncached_failures`. | v7 ran through ≥12 cascade relaunches with provider outages; cached empties would silently survive resume. | `extractor.py`, `orchestrator.py` |
| 7 | **Relation classifier no-response failures propagate.** Transport outages no longer degrade to a semantic `independent/unclear` (which caches a Keep); the conservative fallback applies only when a model actually responded. | Same outage-to-semantics risk on the write path. | `relation.py` `_ResponseTraceLLM` |
| 8 | **Shard retries + append-only logs (R7).** The driver retries failed shards in-place with backoff instead of aborting the cascade, and shard logs append per attempt so tracebacks survive relaunches. | v7's fleet-wide shard failures required manual relaunches, and per-pass log truncation destroyed the root-cause tracebacks. | `run_vllm_cascade.py` `--shard-retries` (2), `--shard-retry-backoff-s` (5.0), `_write_command_header` (append mode) |
| 9 | **Support-coverage telemetry (R2).** Per-question extras now record `retrieval_support_coverage_before_trim` and `answer_context_support_coverage`, making the retrieval-coverage ceiling a first-class run metric. | Coverage was decisive in v7 (0/20 correct under imperfect coverage) but had to be reconstructed post hoc. | `orchestrator.py` answer extras |

## Run

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
bash deploy/run_lme_m_strat30_5systems.sh
# -> runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v8
```

Same slice (`data/slices/longmemeval_m_strat30_seed0.jsonl`), same judge
(gemma-4-31b-it) with the corrected guards (multiplicative number words,
head-anchored abstention detection — see ANALYSIS_REPORT §2), so v8 numbers are
directly comparable to the adjudicated v7 numbers (controller 61.1%, b4 63.3%).
Reproduce v7 exactly with `V8_FIXES=0`.

What to look at first in the v8 results: the knowledge-update current-vs-historical
split (does lineage separate controller from b4?), bucket D (post-retry refusal
count under the 35B escalation), and the new coverage extras vs accuracy.
