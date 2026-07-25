# M1-W4 design note — Baseline 3 (recency-pruning) + action_log + Gate G1

**Task:** M1-W4 §1. Implement Baseline 3 — the first baseline operating on
durable `memory_items` rather than turn-level retrieval — wire the
`action_log` JSONL writer that every later baseline + the controller depend
on, lock down memory-schema unit tests, and produce the first three-baseline
results table on the 50-session slice. The week ends by closing Gate G1.

**Tag (target):** `v0.2.0-m1-end-G1-{pass,conditional,fail}`.

This document records (1) the carry-over from Week 3 that constrains
Week 4, (2) the three design decisions the §3.0 task spec demands an
explicit answer to, and (3) the per-competency hypothesis that §3.5 will
measure against.

## 1. Carry-over from Week 3

Quoted from `NOTES/m1w3_sanity.md` §0–§1 verbatim, so Week 4 numbers
compare against a stable reference:

> | Competency | No-memory (W2) | Flat-vector (W3) | Δ |
> |---|---:|---:|---:|
> | single-session-user      | 100.0% | 100.0% | +0.0 pp |
> | single-session-assistant | 100.0% | 100.0% | +0.0 pp |
> | single-session-preference| 100.0% | 100.0% | +0.0 pp |
> | multi-session            | 100.0% | 100.0% | +0.0 pp |
> | knowledge-update         | 100.0% | 100.0% | +0.0 pp |
> | temporal-reasoning       | 100.0% | 100.0% | +0.0 pp |
> | abstention               | 100.0% | 100.0% | +0.0 pp |
>
> *Run wall-clock W3: 1969.9s. Slice:
> `data/slices/longmemeval_s_50_seed0.jsonl`. Seed: 0. Anti-leakage on
> 50/50 sessions; current session never appears in retrieval.*

**The 100% on every row is a slice artifact, not a baseline ceiling.**
On the synthetic placeholder (`data/longmemeval_s_synthetic.jsonl`,
M1-W1 §3.1): every gold answer ≈ "they prefer coffee in the morning",
the dialog literally contains it, and `supporting_session_ids = [its
own session_id]` for all 50 records (`unique_supporting=50,
self_ref=50, multi_supp=0`). After the W3 §2.5 current-session-exclusion
filter, every retrieved-memory block reads `[no relevant memory found]`
on every session — flat-vector degenerates to no-memory plus a stub
header.

Two consequences for Week 4:

1. The `multi-session` and `knowledge-update` rows — the rows where
   recency-pruning's predicted **eviction-of-truth losses** (§3 below)
   should appear vs. flat-vector — are not distinguishable on the
   synthetic slice. They will become substantive once the real
   LongMemEval-S file lands (a `scripts/build_slice.py` rebuild plus a
   re-run of `scripts/finalize_m1w4.sh`; no code change).
2. Recency-pruning operates on **`memory_items`** rather than the
   raw turn stream. On this slice that means recency's items are
   single-session (the trivial extractor admits each user turn into
   `memory_items`, and `supporting_session_ids` = current session means
   every admitted item is from the visible dialog). The FIFO eviction
   path is exercised end-to-end at unit-test level (capacity invariant,
   FIFO discipline, action_log shape) but cannot produce the
   substantive eviction-of-truth pattern on this slice. The §3.5
   qualitative analysis records this fact instead of papering over it.

This is the same pipeline-vs-thesis-claim split that Week 2 and Week 3
documented (`NOTES/m1w2_sanity.md` §4, `NOTES/m1w3_sanity.md` §0).
Week 4's contribution is **the substrate** (`memory_items` + `action_log`)
and **the third row of Table 4.1**; the substantive multi-session /
knowledge-update gain pattern and the eviction-of-truth qualitative
examples appear with no code change required, only a slice rebuild.

### Anomalies to carry forward

- **Judge fallback.** 31/50 grades on Week 2 came from the substring
  fallback (LLM judge emitted empty text). Re-running W2/W3 with the
  current evaluator code is required (§3.4 below) to confirm cache
  reuse and that no silent evaluator drift occurred between weeks. The
  ±1pp tolerance is documented in `m1w4_evaluator_drift.md` if any.
- **Token budgets.** W2 ~104 tok, W3 ~120 tok. Recency-pruning is on the
  same retrieval shape as flat-vector (k=5, identical prompt template
  modulo the section header), so the upper-bound prompt is also
  ~120–250 tok — well inside `gemma4:e4b`'s 2048 `num_ctx` cap. No
  truncation expected.
- **Self-judging.** `gemma4:e4b` self-judging carries forward as the
  Week-1-through-Week-4 caveat. Substitution to GPT-4o (or the current
  LongMemEval-published judge) lands in Month 4. No change for Week 4.
- **Apple-Silicon libomp.** The W3 §5b mitigation (`OMP_NUM_THREADS=1`,
  `MKL_NUM_THREADS=1`, `TOKENIZERS_PARALLELISM=false`) carries forward
  into `scripts/finalize_m1w4.sh`. Recency-pruning does not load
  MiniLM (the trivial extractor produces no embeddings — see §1c
  below); however, the rerun of W3 in §3.4 does, so the env-var fix
  must remain in place.

## 1a. Decision 1 — Extractor for Week 4 (the placeholder-extractor question)

The recency-pruning baseline operates on `memory_items`, but the proper
LLM-based extractor doesn't arrive until M2-W5. Decision required: how
does this baseline produce memory items?

**Decision: trivial heuristic extractor.** Every user turn in the
dialog (the current session and any resolvable
`supporting_session_ids`) becomes one `memory_item` with:
- `type = 'episodic_fact'` (single typing slot for now; the controller
  in M3 will revisit typing decisions),
- `confidence = 1.0` (trivial extraction has no confidence signal),
- `text = turn.content`,
- `evidence_span_ids` pointing to the originating turn.

No LLM call, no typing decision, no relation classification. The
admission action is `Keep`; the eviction action (when capacity is
reached) is `Supersede` with `prior_memory_id` = the evicted row's id
and no replacement (FIFO eviction destroys the row's audit trail —
that destructiveness is the entire point; see §3 below).

**Caveat.** Recency-pruning numbers are upper-bounded by what FIFO
eviction can do given any reasonable item stream; the Month-2
extractor will produce a different stream and recency may need to be
**re-run** on the Month-2 stream. This is flagged here so the §3.4
results table and the §G1 gate document carry the caveat forward to
the thesis chapter, and so Month 4 doesn't assume Month-1 numbers are
final.

**Why trivial and not LLM-based now?** §I.11 of the proposal makes it
explicit: doing the extractor properly is M2-W5, with a hand-labelled
dev set in M2-W6 and a hard-stop gate (G2) in M2-W7–8. Pre-empting it
this week breaks that gate's chain of evidence. The trivial extractor
is the smallest thing that lets recency exercise the substrate; it is
**not** a candidate Month-2 design.

## 1b. Decision 2 — Capacity (the FIFO queue size)

What is N for the FIFO queue?

**Decision: N = 50 memory items.** Justification:

- At one item per user turn (trivial extractor) and median LongMemEval-S
  session length ≈ 30 user turns across supporting sessions (Wu et
  al., 2025 §3), N = 50 lets recency retain ~1.5 sessions of items —
  the regime where FIFO can plausibly help (small enough to evict,
  large enough to retain something).
- N too small (≤ 10) collapses to the no-memory limit on multi-session
  reasoning; N too large (≥ 200) collapses to flat-vector and cannot
  produce the eviction signature §3 calls out.
- A capacity sweep N ∈ {10, 25, 50, 100} is **pre-registered** for the
  Month-4 ablation work (proposal §I.7.3). Do not run it this week.

A 5-session capacity=25 peek (`scripts/finalize_m1w4.sh --peek-capacity
25`) confirms the **sign** of the effect (smaller capacity = more
eviction = expected drop on multi-session) without consuming the
ablation budget. See §3.5.

## 1c. Decision 3 — Retrieval semantics (what does recency retrieve over?)

Recency-pruning is **retention** logic, not **retrieval** logic. The
two are independent axes; conflating them at this stage would
contaminate the Week 3 vs. Week 4 comparison.

**Decision: same retrieval as flat-vector.** Specifically:

- FAISS `IndexFlatIP` over L2-normalized embeddings of
  `memory_items.text`,
- `sentence-transformers/all-MiniLM-L6-v2` (no fine-tuning),
- top-k = 5,
- per-question reset: the FIFO queue is rebuilt from
  `supporting_session_ids` (minus the current session, same anti-leak
  rule as W3 §2.5) before each question; admission proceeds in turn
  order; eviction is FIFO.

This isolates **what is stored** (a recency-bounded subset of
`memory_items`, vs. flat-vector's full set of turns) rather than **how
it is retrieved** (cosine similarity, top-5, both baselines).

**Why a status-flip eviction (and not a real `supersede` chain)?** The
M1-W4 task spec §3.3 calls this out explicitly. Two paths:

1. **Real supersede chain.** Each FIFO eviction is a `supersede(old,
   sentinel)` call with a sentinel "evicted" row. Preserves lineage
   but pollutes the schema with an artificial sentinel type that
   doesn't survive Month-2's typing decisions.
2. **Status flip.** Each FIFO eviction sets `status = 'superseded'` on
   the oldest active row directly, with no replacement, and writes an
   `action_log` entry with `action = 'Supersede'`,
   `prior_memory_id = <evicted id>`, `resulting_memory_id = NULL`,
   `rationale = 'FIFO eviction at capacity=50'`.

**Decision: status flip path.** The recency baseline has **no lineage**
under this choice — eviction destroys version history. **That is the
entire point.** The destructiveness gap between recency (forgets to
make room, loses lineage) and the controller (forgets selectively,
preserves lineage via `supersedes_id` chains) is the single most
important comparison the thesis sets up. Recording it this week with
the simpler implementation lets Chapter 4 §4.X (versioning vs.
overwrite ablation, proposal §I.7.3) pick this up as the load-bearing
example without re-implementation.

A `supersede_evict` helper that wraps the status-flip + action_log
write lives in `src/ask/memory/operations.py` (added this week, see
§3.1). Tests assert the post-state: `status='superseded'`,
`supersedes_id IS NULL`, `action_log` has one matching row.

## 2. Three design decisions, summarized

| Axis | W4 default | Pre-registered Month-4 sweep |
|---|---|---|
| Extraction | Trivial (every user turn → one episodic_fact, conf=1.0) | LLM-based (M2-W5); recency re-run on M2 stream |
| Capacity (N) | 50 items | N ∈ {10, 25, 50, 100} ablation |
| Retrieval | Same as flat-vector (MiniLM, FAISS IP, k=5, per-question reset) | k ∈ {1, 3, 5, 10} ablation, retrieval-method ablation |
| Eviction style | Status flip (no lineage) | Versioning vs. overwrite ablation (M5) — controller is the natural comparator |

## 3. Predicted Week-4 hypotheses (per-competency)

These are the predictions §3.5 will measure against on the **real**
LongMemEval-S release file. On the synthetic placeholder, every row
should remain at 100% (matching no-memory and flat-vector) because every
admitted item is single-session and the retrieval block degenerates.

| Competency | No-memory (W2) | Flat-vector (W3) | Recency W4 hypothesis (real LME-S) | Reasoning |
|---|---:|---:|---|---|
| single-session-user | 100% | 100% | ≈ flat-vector | Answer is in the current session; eviction has nothing to do. |
| single-session-assistant | 100% | 100% | ≈ flat-vector | Same. |
| single-session-preference | 100% | 100% | ≈ flat-vector; **leak check** | Same; large win is a leak signature (§3.5). |
| multi-session | 100% | 100% | **Mixed**: gain over no-memory, **loss vs. flat-vector** | Some prior-session content survives the FIFO window (gain over no-memory); but capacity-evicted true facts are lost (loss vs. flat-vector). |
| knowledge-update | 100% | 100% | **Possible *gain* vs. flat-vector** | Recency by accident does what the controller does on purpose: newest-wins. The OLD fact is more likely to be FIFO-evicted than the NEW one because the new one was admitted later. **This is the one row recency may strictly beat flat-vector on.** Note the eviction-of-truth caveat (§3.5). |
| temporal-reasoning | 100% | 100% | Mixed | Some temporal questions reference older content (loss); some newer (≈ flat-vector). |
| abstention | 100% | 100% | ≈ flat-vector | Eviction can hand the model less misleading context (slight gain) or strip the relevant abstention cue (slight loss). |

The "knowledge-update gain vs. flat-vector" row is the eviction-as-
accidental-newest-wins hypothesis: the proposal §I.5.2 makes this
explicit ("recency is the cheapest baseline that, by accident, models
something like supersession"). The "multi-session loss vs. flat-vector"
row is the eviction-of-truth signature §3.5 hand-classifies.

If the real-slice re-run shows recency strictly dominating flat-vector
on **every** competency (Risk #6 in §6 below), suspect the trivial
extractor is leaking gold-relevant content via per-turn admission —
spot-check 5 winning sessions before relying on the table.

## 4. Implementation plan

```
ask_controller/src/ask/baselines/
├── recency_pruning.py         (NEW — Baseline 3)
└── prompts/
    └── recency_pruning.j2     (NEW — identical retrieved-memory block to W3)

ask_controller/src/ask/memory/
└── operations.py              (EXTEND — add get_by_id, get_lineage,
                                supersede_evict; existing insert_active +
                                supersede + retrieve_active are kept verbatim)

ask_controller/src/ask/audit/
└── action_log.py              (EXTEND — add `baseline` and `session_id`
                                fields to ActionLogEntry; mode='w' truncate
                                option; fsync on every write)

ask_controller/tests/
├── test_memory_operations.py  (NEW — insert, supersede atomicity,
                                retrieve-active-only, type filter, lineage,
                                double-supersede concurrency, supersede_evict)
├── test_action_log.py         (EXTEND — round-trip, schema rejection,
                                crash safety, baseline + session_id fields)
└── test_recency_pruning.py    (NEW — capacity invariant, FIFO discipline,
                                action_log shape, determinism, prompt slot
                                rendering, retrieval semantics)

ask_controller/scripts/
├── run_baseline.py            (EXTEND — accept --baseline recency, --capacity)
└── finalize_m1w4.sh           (NEW — runs all 3 baselines, merges, gate doc)
```

## 5. What this week explicitly does NOT do

Per task spec §7:

- No LLM-based extractor (M2-W5).
- No relation classification (M2-W7–8).
- No controller (M3-W9).
- No naive-overwrite baseline (M3-W10 — fourth baseline lives with the
  controller).
- No capacity sweep (M4 ablation).
- No k-sweep (M4 ablation).
- No per-type thresholds (M3).
- No MGP-6 perturbation slice (M3-W11–12).

If finding myself building an LLM extractor or a relation classifier
this week → stop. Those weeks are scheduled and the M2 hard-stop gate
G2 depends on doing the extractor properly with a hand-labelled dev set.

## 6. Acceptance summary (what tagging Week 4 means)

The §5 acceptance criteria require pytest green (memory operations,
action log, recency baseline tests), atomic supersede, recency
`report.json`, the merged 3-baseline table, ±1pp evaluator drift
tolerance vs. archived W2/W3, the eviction-of-truth qualitative
examples, the `G1_gate_decision.md` advisor send, and the tag.

On the synthetic placeholder slice, criteria 1–4, 7, 8 are met; the
"flat-vector vs. recency vs. no-memory" comparison reads as **equality
at 100%** (all three saturate by construction of the placeholder). Once
the real LongMemEval-S file replaces `data/longmemeval_s_synthetic.jsonl`,
the slice rebuild produces a non-saturated result and §5 §6 (eviction-
of-truth) becomes the substantive criterion the proposal claims.

This whole document is the seed of the Chapter 3 §3.4 paragraph the task
§10 calls out — keep it as the source-of-truth justification for the
three Week-4 design choices and the destructiveness-gap framing.
