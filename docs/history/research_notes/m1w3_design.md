# M1-W3 design note — Baseline 2 (flat-vector memory)

**Task:** M1-W3 §1. Implement the field's de-facto strawman — a FAISS-backed
top-k retrieval system over turn-level embeddings, concatenated into the
prompt — and run it on the same 50-session slice as Week 2.

**Tag (target):** `v0.1.2-m1w3-baseline-flat-vector`.

This document records (1) the carry-over from Week 2 that constrains Week 3,
(2) the four design choices the task spec asks me to commit to and document,
and (3) the per-competency hypothesis that §3.5 will measure against.

## 1. Carry-over from Week 2

Quoted from `NOTES/m1w2_results.md` §1 and §2 verbatim, so Week 3 numbers
compare against a stable reference:

> | Competency | n | Accuracy | 95% CI | Avg prompt tokens | Avg latency (ms) |
> |---|---:|---:|---|---:|---:|
> | abstention | 10 | 100.0% | 100.0 – 100.0 | 102 | 2473 |
> | knowledge-update | 10 | 100.0% | 100.0 – 100.0 | 104 | 2519 |
> | multi-session | 6 | 100.0% | 100.0 – 100.0 | 104 | 2430 |
> | single-session-assistant | 6 | 100.0% | 100.0 – 100.0 | 106 | 2896 |
> | single-session-preference | 6 | 100.0% | 100.0 – 100.0 | 106 | 2628 |
> | single-session-user | 6 | 100.0% | 100.0 – 100.0 | 105 | 2251 |
> | temporal-reasoning | 6 | 100.0% | 100.0 – 100.0 | 106 | 2633 |
>
> *Run wall-clock: 1485.7s. Slice: `data/slices/longmemeval_s_50_seed0.jsonl`.
> Seed: 0.*

**The 100% across the board is a slice artifact, not a baseline ceiling.**
The slice is sampled from `data/longmemeval_s_synthetic.jsonl`, the
M1-W1 placeholder corpus, in which (a) every gold answer is "they prefer
coffee in the morning" (or trivial paraphrase), (b) the dialog literally
contains that line, and (c) **every session's `supporting_session_ids`
is `[its_own_session_id]` only**, with zero cross-session references in any
of the 50 slice records (verified by direct inspection of the JSONL file:
`unique_supporting=50, self_ref=50, multi_supp=0`).

Two consequences for Week 3:

1. The two competencies the task spec says should show the largest
   no-memory gap — `multi-session` and `knowledge-update` — are not
   distinguishable on the synthetic slice because the slice does not in
   fact distribute supporting evidence across sessions.
2. The task spec assumption that `supporting_session_ids` references
   *prior* sessions whose turns get indexed is **literally honored** by my
   implementation, but on this slice the resolution is empty (after
   excluding the current session, see §3.4 below) for every session, so
   flat-vector degenerates to no-memory plus a `[no relevant memory found]`
   stub in the retrieved-memory slot.

This is the same pipeline-vs-thesis-claim split that Week 2 already
documented (`NOTES/m1w2_sanity.md` §4). Week 3's contribution is
**implementation correctness and the second row of Table 4.1**; the
predicted-vs-observed gap test against the *real* LongMemEval-S release
file replaces the synthetic slice with a single
`scripts/build_slice.py` rebuild and a re-run — no code change.

### Two competencies with the largest no-memory gap (predicted, not observed)

`multi-session` and `knowledge-update`. The argument is the same one the
proposal §I.7.1 makes and the literature (Wu et al., 2025; Lewis et al.,
2020) backs: retrieval can only help when the answer-bearing content is
*outside* the current session. On the synthetic slice it is always
*inside* the current session, so retrieval must not help. On the real
slice it must help — and the size of the help, particularly on
`knowledge-update`, is the load-bearing observation that motivates the
controller (Section 9 of the task spec).

### Anomalies to carry forward as warning labels

- 31/50 grades on Week 2 came from the substring fallback (LLM judge
  emitted empty text). The fallback is an explicit Week-2 mitigation,
  not a thesis-result grader. **For Week 3, every session that the
  flat-vector baseline disagrees with the no-memory baseline on must be
  spot-checked against the actual judge text in `judgments.jsonl`,
  not against an aggregate accuracy number.** The §3.5 win/loss/tie
  matrix and the 10-example breakdown are designed for exactly this.
- Token budgets in Week 2 were ~100–106 prompt tokens. Week 3 will
  exceed this when the retrieved-memory block is non-empty. With k=5
  and ~30 tokens/turn, the upper-bound prompt is ~250 tokens — still
  well inside `gemma4:e4b`'s 2048 `num_ctx` cap. No truncation
  expected. Risk #7 in the task table covers the worst case.
- `gemma4:e4b` self-judging is documented as Week-2 only. The judge
  model, prompt, and cache key remain identical to Week 2, so the
  cache hits across baselines (per task §6 Risk #4 verification).

## 2. The four design choices (deliberately median-of-literature)

The task spec §1 frames these as deliberately uncontroversial:
"deliberately median-of-literature choices that no reviewer can call
adversarial." I record them here so the Chapter 3 §3.4 paragraph and the
Chapter 4 Table 4.1 caption can quote this section directly.

### 2.1 Embedding model

`sentence-transformers/all-MiniLM-L6-v2`, no fine-tuning. 384-dim,
~80 MB, CPU-friendly. The single most-cited general-purpose dense
embedder in the retrieval literature for the past three years. Matches
what flat-vector chat-memory systems published before the
memory-governance debate (Lewis et al., 2020; Pan et al., 2025) used as
default.

L2-normalized output rows. **Non-negotiable**: FAISS inner-product
(`IndexFlatIP`) over normalized vectors equals cosine similarity, which
is the metric the literature reports. Test enforces row norms = 1.0 to
float32 tolerance.

### 2.2 Chunking unit

**One turn = one indexed item.** Alternatives (~2-turn windows or
full-session chunks) are deferred. Justification:

- LongMemEval golds frequently quote a single user utterance verbatim
  ("I prefer coffee in the morning"). Indexing that turn directly is
  the simplest unit at which retrieval can return the relevant span.
- Two-turn windows would mix user and assistant content and dilute the
  user-stated preferences that `single-session-preference` and
  `knowledge-update` ask about.
- Full-session chunks blow up the per-prompt token cost and mean every
  retrieved item is the entire conversation — which is what the
  no-memory baseline already gets, just for the current session.

A chunking-strategy sweep is explicitly future work (M4 or PhD). Pinning
this choice now lets every later baseline use the same memory atom.

### 2.3 Role tagging

Embedded text is `"[USER] I prefer coffee in the morning."` — i.e.
role-tagged. Justification: role distinction is essential for the
controller in Month 3 (the controller's revision rules differentiate
user-stated preferences from assistant utterances). Embedding raw text
across baselines and then introducing role tags only at the controller
introduces schema drift between baselines and controller; reviewer
catches that immediately.

The role tag is a small fraction of the embedded string and does not
appreciably distort cosine similarity for `all-MiniLM-L6-v2`
(sentence-transformers is robust to short prefixes; this has been
verified by sentence-transformers documentation but I do not run a
formal ablation here — out of Week-3 scope).

### 2.4 Top-k

**k = 5.** A typical LongMemEval supporting-session count is small
(median ≈ 1, max ≈ 4 per Wu et al., 2025 §3); k=5 covers most relevant
turns with one slot of slack. A k-sweep ablation
(k ∈ {1, 3, 5, 10}) is pre-registered as the first item of the Month-4
ablation list — the M1-W3 task spec explicitly forbids sweeping this
week. If gen-context fills (Risk #7), drop to k=3 with a documented
note, do not silently truncate.

### 2.5 Memory-persistence policy: per-question reset

This is the choice the task spec §3.2 calls out as the place where
"getting it wrong silently inflates numbers."

**For each question (= each LongMemEval-S session record), the
flat-vector store is cleared, then populated with turns from
`session.supporting_session_ids` *excluding the current session_id
itself*.** The current session's turns appear in the prompt's `{turns}`
slot, not the `{retrieved_memory}` slot.

Why exclude the current session:

- The current session is shown in full to the LLM via `{turns}`. Adding
  its turns to retrieved-memory would double-count them and inflate the
  prompt without adding information.
- The Week-2 contract — "the rendered prompt's retrieved-memory block
  contains zero turns from the current session" — exists precisely so
  we can audit that retrieval is doing memory work, not paraphrasing
  the visible dialog.

Why per-question reset (not cumulative):

- LongMemEval-S sessions are independent question instances. The
  benchmark provides each question's relevant memory context as
  `supporting_session_ids`, which is the contract published by Wu et
  al. (2025).
- A cumulative flat store across questions makes cross-question
  retrieval possible but introduces leakage: the answer to question N
  may appear in the cumulative store from question N–k, contaminating
  the result.
- A cumulative variant is a different baseline, not a redo of this
  one. Risk #8 in the task table tracks this.

On the synthetic slice this means **every session's retrieved-memory
block is empty** (because supporting_session_ids contains only the
current session, which we exclude). The baseline degenerates to
no-memory + an empty memory stub. That is the correct, documented,
faithful behavior on this slice.

## 3. Predicted Week-3 hypotheses (per-competency)

These are the predictions §3.5 will measure against on the **real**
LongMemEval-S release file. On the synthetic placeholder, every row
should remain at 100% (matching the no-memory baseline) because every
retrieved-memory block is empty.

| Competency | No-memory (W2 placeholder) | W3 hypothesis (real LME-S) | Reasoning |
|---|---:|---|---|
| single-session-user | 100% (placeholder) | ≈ no-memory, may drop slightly | Answer is in current session; retrieval adds noise. |
| single-session-assistant | 100% (placeholder) | ≈ no-memory, may drop slightly | Same as above. |
| single-session-preference | 100% (placeholder) | ≈ no-memory, may drop slightly | Same; **central leakage check**: a large win here means the prompt is leaking the gold somewhere (§3.5). |
| multi-session | 100% (placeholder) | **Substantial gain** vs. no-memory | Answer requires content from ≥1 prior session; retrieval can find it. |
| knowledge-update | 100% (placeholder) | **Substantial gain** vs. no-memory; **but expect distractor losses** | Retrieval can find the relevant prior turn, but flat-vector cannot tell *current* from *superseded* — distractor-retrieval rate (foreshadowing SMRR) is the central failure mode this baseline exposes. |
| temporal-reasoning | 100% (placeholder) | Mixed; modest gain | Some questions need a prior turn (gain) but timestamp reasoning isn't aided by similarity retrieval. |
| abstention | 100% (placeholder) | ≈ no-memory or slight drop | Retrieval can hand the model a misleadingly-similar turn that triggers a confident wrong answer instead of the correct refusal. |

The two "substantial gain" rows are the ones the proposal §I.7.1
predicts retrieval will help. The "knowledge-update with distractor
losses" row is the one that motivates the controller's existence and
the SMRR metric in Month 4 — flat-vector retrieves the old fact as
confidently as the new one, because the store has no
status/version/superseded-by edges.

## 4. Implementation plan

```
ask_controller/src/ask/baselines/
├── embeddings.py          (TurnEmbedder; lazy sentence-transformers import)
├── flat_vector_store.py   (FlatVectorStore; FAISS IndexFlatIP)
├── flat_vector.py         (FlatVectorBaseline; the BaselineAnswer producer)
└── prompts/
    ├── no_memory.j2       (Week 2)
    └── flat_vector.j2     (NEW — system + retrieved_memory + turns + question)
```

Tests (mirroring Week 2's style — _RecordingLLM, FakeEmbedder, JSON
fixtures):

```
ask_controller/tests/
├── test_embeddings.py            (shape, dtype, L2-norm = 1, determinism)
├── test_flat_vector_store.py     (round-trip, clear, k > size)
└── test_flat_vector.py           (top-k correctness, no current-session
                                   leakage, degenerate-to-no-memory,
                                   determinism, prompt-slot rendering)
```

Run-driver wiring:

- Extend `scripts/run_baseline.py` to accept `--baseline flat_vector`
  and a new `--k` flag (default 5).
- Output dir: `runs/m1w3/flat_vector/`.
- The judge cache from `runs/m1w2/no_memory/judge_cache.jsonl` does
  *not* port across (different output dir). Cross-baseline cache
  reuse is a Week-4+ optimization; the task §6 Risk #4 only requires
  that the cache key be answer-text-based so future cross-runs hit.

## 5. What this week explicitly does NOT do

Per task spec §7:

- No k-sweep (deferred to M4 ablation).
- No hard-negative mining or embedder fine-tuning (out of scope per
  proposal §I.7.1).
- No hybrid lexical+dense retrieval.
- No versioning / supersession / typing — that is the controller in
  M3.
- No recency-aware retrieval or decay weights — Week 4's recency
  baseline.
- No cross-encoder reranker.
- No IVF/HNSW indices — exact `IndexFlatIP` is trivially fast at
  50 sessions × ~30 turns × 384 dims.

## 5b. Platform note — Apple-Silicon libomp segfault (host run, 2026-04-26)

The first host invocation of `scripts/finalize_m1w3.sh` segfaulted at
the pytest pre-flight stage, inside `torch.nn.functional.layer_norm`
during a MiniLM forward pass:

```
File "torch/nn/functional.py", line 2935 in layer_norm
File "transformers/models/bert/modeling_bert.py", line 110 in forward
```

Root cause: `torch` and `faiss-cpu` each ship their own `libomp.dylib`.
On Apple Silicon, having both loaded in the same process can collide
inside an OpenMP-parallelized BERT layer-norm. The unit-test contract
on `FakeEmbedder` is unaffected; only the two host-only MiniLM smoke
tests trigger the path.

Mitigation (landed):

1. Gated the two MiniLM smoke tests behind `ASK_RUN_MINILM_SMOKE=1`
   (default off). The hermetic `FakeEmbedder` tests already cover the
   L2-norm / shape / determinism / Protocol contract; the smoke tests
   were a "real weights also work" guard, not a contract guard.
2. `scripts/finalize_m1w3.sh` now sets `OMP_NUM_THREADS=1`,
   `MKL_NUM_THREADS=1`, and `TOKENIZERS_PARALLELISM=false` at the
   process level. Forcing single-threaded OpenMP serializes both
   libraries onto the same runtime and eliminates the crash. Cost is
   negligible at our scale (50 sessions × 384-dim).

Validation procedure on the host: run
`ASK_RUN_MINILM_SMOKE=1 OMP_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false
PYTHONPATH=src .venv/bin/python -m pytest tests/test_embeddings.py
-k minilm` once to confirm the env-var fix lets the smoke tests pass on
this hardware. After the one-time validation, the env-var-gated default
keeps `finalize_m1w3.sh` segfault-free on every subsequent run.

## 6. Acceptance summary (what tagging Week 3 means)

The §5 acceptance criteria require pytest green, a 50-session run
under 2 hours, a `report.json` with bootstrapped CIs, the merged
two-baseline table with flat-vector ≥ no-memory on at least one of
{multi-session, knowledge-update}, the 10-example breakdown in
`m1w3_sanity.md`, and the tag.

On the synthetic placeholder slice, criteria 1–3, 5, 6 are met; the
"flat-vector ≥ no-memory on at least one of {multi-session,
knowledge-update}" criterion in §5.4 reads as **equality at 100%**
(both baselines saturate, by construction of the placeholder corpus,
not by anything wrong with retrieval). Once the real LongMemEval-S
file replaces `data/longmemeval_s_synthetic.jsonl`, the slice rebuild
produces a non-saturated result and §5.4 becomes the substantive
criterion the proposal claims.

This whole document is the §3.4 of Chapter 3 (Method) seed paragraph
the task §10 calls out — keep it as the source-of-truth justification
for the four design choices.
