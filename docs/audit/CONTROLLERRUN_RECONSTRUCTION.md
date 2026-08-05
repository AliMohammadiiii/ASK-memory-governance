# Controller Run Reconstruction, LongMemEval-M

**Purpose.** Reconstruct, stage by stage, the exact pipeline path that produced
the reported LongMemEval-M controller numbers, and document how the headline
`139/180 = 77.2%` figure was assembled. Every claim below is grounded in a file
that was read for this audit; file paths are absolute.

> **Superseding status (ledger v1.1).** This document reconstructs a historical,
> selection-biased `failure_replay_only` artifact; `139/180` is not an eligible
> LongMemEval result. The independent Modal top-up completed 84 of the 110
> carried-forward items and found 71 correct plus 13 regressions. Across the
> 154 observed items, the raw score is 96/154; the full-180 raw bounds are
> 53.3–67.8%, or 55.6–70.0% if the four Codex/GPT-5 overrides are retained.
> These observations do not reproduce 77.2%.

**Evidence roots.**
- Runs (read-only): `external://Master/ask_controller/runs/`
- Canonical source: `repo://src/ask/`
- Drivers: `repo://scripts/run_vllm_cascade.py`,
  `.../scripts/build_v8_adjudicated_report.py`

> Note on repo copies. The live run artifacts live under `ask_controller/`. The
> canonical, published-layout copy of the same code is `ask-memory-governance/`
> (`src/ask/...`). Source citations below use the canonical copy; run artifacts
> are cited from `ask_controller/runs/`.

---

## 1. Pipeline stages (per session), with code anchors

The whole per-session flow is driven by `ControllerOrchestrator.answer()`
(`src/ask/pipeline/orchestrator.py:653`). The eval harness wraps it with
extraction, judging, and scoring. Stages in execution order:

### 1.1 Dataset loading / slice selection
- Slice built once, deterministically, by
  `scripts/build_stratified_slice.py` → `data/slices/longmemeval_m_strat30_seed0.jsonl`
  (30 items/competency × 6 = 180, seed 0). This is documented in
  `V7_FIXES_AND_RUN.md` ("builds the stratified slice once … deterministic under seed 0").
- Sessions are parsed into `LongMemEvalSession` objects by
  `src/ask/data/longmemeval.py`.
- Slice/range selection and sharding are argument-driven in
  `scripts/run_vllm_cascade.py` (`--slice`, `--sample-from/-to`, `--shards`) and
  passed down to `scripts/run_baseline.py` per shard
  (`_base_cmd`, `_shard_cmd` at `run_vllm_cascade.py:56,234`).

### 1.2 Prompt construction (extraction)
- `Extractor.render_prompt()` (`src/ask/extraction/extractor.py:202`) renders the
  per-turn extraction prompt with a strict JSON schema
  (`ExtractionOutput.model_json_schema()`).

### 1.3 Extraction / candidate generation
- `ControllerOrchestrator._extract_turns()` / `._extract_turn()`
  (`orchestrator.py:1361,1399`) call `Extractor.extract()`
  (`extractor.py:118`) per user turn. v7 §5-fix-1 made this concurrent
  (`--extraction-concurrency`, default 8; `run_vllm_cascade.py:527`).
- Prefilter: `_prefilter_memory_turns()` (`orchestrator.py:1132`) keeps the
  top-64 turns by question similarity (`--controller-memory-top-k 64`).
- Cross-run reuse: content-keyed shared extraction cache
  (`orchestrator.shared_extraction_cache_path`; merged by
  `_merge_shared_extraction_cache`, `run_vllm_cascade.py:375`), seeded
  controller→b4 in run order.
- **Integrity behaviour (v8):** on a provider no-response, `extract()` raises
  instead of caching a fabricated empty extraction
  (`extractor.py:145-162`). Under v7 those failures were cached as empty
  (see the Failure Ledger).

### 1.4 Controller decisions (Keep / Supersede / Abstain)
- `_process_candidate()` (`orchestrator.py:1530`) drives, per candidate memory:
  1. relation classification `_classify_relation()` (`orchestrator.py:1572`) →
     `RelationClassifier.classify()` (`src/ask/classifier/relation.py:70`), a
     two-stage classifier with optional cascade escalation
     (`_should_escalate`, `orchestrator.py:1615`);
  2. prior selection `_find_prior` / `_select_prior_relation`
     (`orchestrator.py:1721,1743`);
  3. the scored three-action rule `controller.policy.decide()`
     (`src/ask/controller/policy.py:39`): `if S_abs>θ_abs: ABSTAIN;
     elif S_rev>θ_sup and relation_update>0: SUPERSEDE; else KEEP`
     (feature scoring in `src/ask/controller/scoring.py` / `score.py`);
  4. `_execute_decision()` / `_write_decision()` (`orchestrator.py:1872,1907`).

### 1.5 Memory persistence
- SQLite-backed store operations in `src/ask/memory/operations.py`:
  `insert_active` (`:34`), `supersede` (`:76`, links lineage, marks prior
  inactive), `supersede_evict` (`:155`), `retrieve_active` (`:199`,
  excludes superseded), `get_lineage` (`:234`).

### 1.6 Retrieval / ranking
- `_retrieve()` (`orchestrator.py:1942`) does dense retrieval (MiniLM-L6-v2,
  `max_seq_length 256`, k=16) with `_augment_retrieval` (`:2171`), ±2 neighbor
  expansion (`_expand_retrieval_neighbors`, `:3125`), assistant/raw-user context
  pools (`_assistant_context_items` `:2068`, `_raw_user_context_items` `:2099`),
  and **query-gated historical lineage** (`_historical_context_items` `:2025`,
  gated by `_requests_historical_memory` `:248`, v8).

### 1.7 Answer-context compilation
- `_rerank_for_answer()` (`:2327`) → `_session_diverse_answer_order()` (`:2339`,
  v8 R6 cross-session diversity) → `_budget_trim_for_answer()` (`:2382`) trims to
  ~12k tokens (`--answer-context-max-tokens 12000`). Token budget estimated by
  `_estimate_prompt_tokens` (`:335`, tiktoken-when-available, v7 §4-fix-7).
- Prompt assembled by `_render_prompt()` (`:2463`), plus deterministic
  `_temporal_block` (`:2493`), `_conflict_block` (`:2861`), and
  `_current_location_block` (`:2943`, suppressed for historical questions in v8).

### 1.8 Answer generation
- `answer()` (`:653`) calls the answerer (qwen3.5-9b, temp 0, WORK→FINAL
  scaffold, per-competency prompts). Optional deterministic paths:
  `_compute_answer` (`:2535`), `_aggregation_scaffold` (`:2568`, disabled in v8),
  `_ordinal_list_evidence` (`:2645`). Unknown-retry via
  `_answer_needs_retry` (`:3115`) and `answer_escalation_llm`
  (a genuinely stronger model **only** if configured, see §3).

### 1.9 Judge requests / fallbacks
- `LongMemEvalGrader.grade()` (`src/ask/eval/longmemeval.py:646`) applies, in
  order: blank guard (`:652`), degenerate guard (`:668`,
  `looks_degenerate_answer` `:531`), refusal guard (`:686`), abstention guard
  (`:702`), then the token guard. Abstention routing uses
  `_looks_like_abstention_gold()` (`:552`, head-anchored to first 40 chars).

### 1.10 Parsing / number normalization
- `_normalize_text()` (`:508`) lowercases, strips thousands separators, and
  collapses spelled-out cardinals + multiplicatives via `_collapse_number_words`
  (`:454`) and `_MULTIPLICATIVE_NUMBER_WORDS = {"once":"1","twice":"2","thrice":"3"}`
  (`:451`). The hard gold-token reject (`[gold-token-guard]`) now fires **only**
  on a provable numeric conflict (`:734-755`); all lexical/entity/date
  mismatches defer to the semantic LLM judge.

### 1.11 Scoring / aggregation
- `build_eval_report()` (`:904`) aggregates `GradeResult`s into per-competency
  accuracy + bootstrap CIs, plus answerable/abstention decomposition. Serialized
  to `report.json` / `results.md`.

### 1.12 Retry / resume / replay / shard merge
- Per-shard resume via `run_baseline --resume`; failed shards retried in-place
  with backoff (`_run_logged_with_retries`, `run_vllm_cascade.py:280`;
  `--shard-retries 2`), append-only logs (`_write_command_header`, `:258`).
- Shard union rebuilt by `merge_run_shards()` (`src/ask/eval/merge.py:57`),
  which dedups judgments by `session_id` and rebuilds the report from the union
  of grades.

### 1.13 Adjudicated merge (v8 headline artifact)
- `scripts/build_v8_adjudicated_report.py` merges the 70-item failure replay into
  the 180-item v7 base and rebuilds all statistics (see §4).

---

## 2. Run lineage (v3 → v8 adjudicated)

```
                    LongMemEval-M controller lineage (all judge=gemma-4-31b-it unless noted)

 v3  10-19  (n=10)  5/10  =50.0% ── partial range probe ─┐
 v3  20-29  (n=10)  4/10  =40.0% ── partial range probe ─┤
 v4  100-129(n=30) 17/30  =56.7% ── partial range        ├─► early diagnostics; superseded
 v5  "100_129" dir  ABORTED (KeyboardInterrupt); dir MISNAMED, actually holds
      range_200_239.jsonl; no merged report.json ── UNUSABLE
 v6  200-239(n=40) 29/40  =72.5% ── partial range; fed the v7 fix list (§4/§5)
                                        │
                                        ▼
 v7  strat30 (n=180)  full 6x30 stratified, 5 systems (b1..b4, controller)
      controller: 108/180 (pre-adj)  ──►  110/180 = 61.1% (post-v7-adjudication,
      2 items overridden: 5c40ec5b, 58ef2f1c)   [DIAGNOSTIC ONLY]
      provider contamination: 736 error traces, 316 HTTP-402, 388 empty fallbacks
                                        │
             ┌──────────────────────────┴───────────────────────────┐
             ▼                                                        │
 v8 replay INVALID  (lme_m_modal_qwen35_9b_v8_failures)               │
   0 completed predictions: (1) MiniLM sig-11 shard deaths,          │
   (2) Qwen thinking mode burned the 512-tok budget ── see INVALID.md│
             │ corrected config (shared MiniLM, enable_thinking:false)│
             ▼                                                        │
 v8 replay COMPLETE (lme_m_modal_qwen35_9b_v8_failures_nothink)       │
   replays the 70 v7 controller failures; judge = Qwen/Qwen3.5-9B     │
   25/70 = 35.7% machine ──────────────┐                             │
                                        ▼                             ▼
 v8 topup110 x2 (modal 84/110, openrouter 3/110)      v7 base 180 (110 correct retained)
   INCOMPLETE, no merged report.json                              │
                                        └──────────► MERGE ◄────────┘
                                          build_v8_adjudicated_report.py
                                                    │
                                                    ▼
 v8 adjudicated (lme_m_v8_failure_replay_adjudicated)
   raw   : 110 retained + 25 machine        = 135/180 = 75.0%
   final : 110 retained + 25 machine + 4 overrides = 139/180 = 77.2%  [INELIGIBLE HISTORICAL CONSTRUCTION]
```

Per-run numbers are copied verbatim from the merged `report.json` files; see
`artifacts/controller_run_comparison.json` in this repo for the machine-readable
table.

---

## 3. Why v7 is "diagnostic only", not a clean run

Per `runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v7/ANALYSIS_REPORT.md`
(Revision 3, §5) and confirmed by a direct scan of
`controller/extraction_trace.jsonl` performed for this audit:

- **11,505** extraction traces total; **736** carry an `error` field.
- **316** of those errors contain `402` (HTTP 402 insufficient-credit); the
  report states "at least 315".
- **388** traces are empty extractions with **zero** model responses, provider
  no-responses that v7 cached as valid "no memory" judgments.
- At least **12** cascade relaunches; relation no-responses were likewise
  converted to `independent/unclear` (a cached Keep).
- The v7 escalate-on-Unknown retry was a **no-op**: the run set
  `BIG_MODEL == FAST_MODEL` (`qwen/qwen3.5-9b`), so "escalation" re-asked the
  same 9B (V7_FIXES_AND_RUN.md run block; `run_vllm_cascade.py:217-221` gates
  relation escalation on `big_model != fast_model`).

These provider failures could change both memory state and answers, so the
report labels v7 "diagnostic only, not a clean paper run".

---

## 4. Exactly how the ineligible 139/180 construction was assembled

Source: `scripts/build_v8_adjudicated_report.py` (`main()`, `:285`) and the
resulting `runs/lme_m last version/lme_m_v8_failure_replay_adjudicated/`
`summary.json` + `manifest.json`.

1. **Base = v7 controller (post-v7-adjudication).** Reads
   `base_run/controller/judgments.jsonl` (180 rows, 110 `correct=True`). The
   `failed_ids` set is the 70 rows with `correct=False`
   (`build_v8_adjudicated_report.py:295`).
2. **Replay = the 70 v7 failures.** Reads
   `replay_run/controller/judgments.jsonl` (70 rows, judge **Qwen/Qwen3.5-9B**).
   The script asserts `failed_ids == set(replay)` exactly
   (`:298-303`; `manifest.counts.replay_ids_equal_base_failure_ids: true`).
   Machine-correct in replay = **25/70** (`summary.longmemeval.replay.machine_correct`).
3. **Merge (raw).** For each of the 180 base rows, replace with the replay row if
   the session was a base failure, else keep the base row
   (`merged_raw`, `:310`). Result: 110 retained-correct (Gemma-4-31b judgments)
   + 25 replay-correct (Qwen judgments) = **135/180 = 75.0%**
   (`controller_raw/report.json`).
4. **Merge (adjudicated).** Same merge, but 4 replay rows are overridden to
   `correct=True` by `adjudicate()` (`:92`) using the hard-coded `OVERRIDES`
   dict (`:25`). Result: 110 + 25 + **4** = **139/180 = 77.2%**
   (`controller/report.json`, `overall_accuracy 0.7722222`).

**The four overrides** (from `adjudication_overrides.jsonl`; judge label
"Codex/GPT-5 independent semantic adjudication"):

| session_id | competency | gold (abridged) | prediction | machine verdict → override |
|---|---|---|---|---|
| `07741c44` | knowledge-update | "under my bed" | "under their bed" | wrong → correct (pronoun shift only) |
| `118b2229` | single-session-user | "45 minutes each way" | "90 minutes" | `[gold-token-guard]` → correct (round-trip) |
| `9a707b81` | temporal-reasoning | "21 days. 22 … also acceptable" | "21" | `[gold-token-guard]` → correct (gold's own rule) |
| `gpt4_59c863d7` | multi-session | "…five model kits…(scales…)" | "5" | `[gold-token-guard]` → correct (count-only Q) |

**Replay-quality stats** (`summary.longmemeval.replay`): machine 25/70 (35.7%),
adjudicated 29/70 (41.4%), 4 overrides, machine↔adjudicator agreement 94.3%,
Cohen's κ = 0.880.

### Why 139/180 is an ineligible failure-replay construction, not a result

- **Two different judges in one number.** 110 of the 180 verdicts come from
  **Gemma-4-31b-it** (v7, retained verbatim); the other 70 come from
  **Qwen/Qwen3.5-9B** (the v8 replay). `report.json.judge_model_id` literally
  reads "machine judgments plus four documented Codex/GPT-5 semantic
  adjudications". This is not a single-judge protocol.
- **Two rounds of post-hoc overrides stacked.** The 110 "retained" already bake
  in the earlier v7 overrides of `5c40ec5b` and `58ef2f1c`; the replay adds four
  Codex/GPT-5 semantic overrides. Those four were not independent-human
  annotations and must not be described as human or manual adjudication. The
  `_raw_` 135 figure still contains the two v7 overrides.
- **Only the failures were re-run.** The 110 v7-correct sessions were never
  re-executed under the corrected (v8, fail-closed, `enable_thinking:false`)
  pipeline; they carry forward v7's provider-contaminated memory state. The
  merge patches only the subset that had failed.
- **Different infra / model family per half.** The replay ran on Modal with
  `Qwen3.5-9B` judging; the base ran on OpenRouter with Gemma judging. Latency
  and prompt-token means in the merged report are a blend of the two.
- Consequently `77.2%` is a selection-biased historical construction, not a
  benchmark estimate or defensible upper bound. The observed top-up regressions
  yield 96/154 raw across observed items and full-180 raw bounds of 53.3–67.8%
  (55.6–70.0% with the four Codex/GPT-5 overrides); they do not reproduce the
  construction. The v7 ANALYSIS_REPORT §7 already states a Tier-1 claim "must
  rest on a fresh frozen run, not on corrected numbers."

### One provenance defect to flag
`manifest.json` and `summary.json` record
`provenance.replay_run = "runs/lme_m_modal_qwen35_9b_v8_v7_failures_nothink"`
and the matching `replay_dataset` path. **That directory does not exist.** The
actual completed replay is
`runs/lme_m last version/lme_m_modal_qwen35_9b_v8_failures_nothink`
(note: no `_v7_` segment, and it lives under `lme_m last version/`). The path in
the artifact is therefore not runnable as-is; the reconstruction here uses the
real directory. (This matches the write-target named in
`lme_m_modal_qwen35_9b_v8_failures/INVALID.md`, which itself points at the
never-created `..._v8_v7_failures_nothink` name.)
