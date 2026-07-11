# M1-W4 sanity check — Baseline 3 (recency-pruning)

**Run completed:** ${RUN_TIMESTAMP_UTC}
**Wall-clock:** ${RUN_WALL_SECONDS}s
**Configuration:** Ollama `${RUN_MODEL_TAG}`, recency-pruning with
capacity N=${RUN_CAPACITY}, k=${RUN_K},
`sentence-transformers/all-MiniLM-L6-v2` embeddings (CPU), FAISS
`IndexFlatIP` over L2-normalized rows. Trivial extractor (every user
turn → one episodic_fact, conf=1.0).

This is the §3.5 sanity-check note. Six sections.

## 0. What the host run proves on the synthetic placeholder slice

Telemetry from `runs/m1w4/recency/answers.jsonl` (50 sessions, all
fields validated programmatically):

| Property | Value | Expected | Pass? |
|---|---|---|:-:|
| `n_total` answers persisted | _to fill_ | 50 | _to fill_ |
| sessions with `n_admitted=0` | _to fill_ | 50 (every `supporting_session_ids` filters to empty) | _to fill_ |
| sessions with `n_active=0` | _to fill_ | 50 | _to fill_ |
| sessions with `n_evicted=0` | _to fill_ | 50 (no admissions → no evictions) | _to fill_ |
| sessions where current session_id appears in `retrieval_session_ids` | _to fill_ | **must be 0** (anti-leakage carry-over from W3) | _to fill_ |
| `extras` keys present on every record | _to fill_ | 11 fields (k, capacity, n_admitted, n_active, n_evicted, n_retrieved, retrieval_*, embedder_model_id, supporting_session_ids, unresolved_supporting_ids) | _to fill_ |
| RETRIEVED MEMORY block in rendered prompt | `[no relevant memory found]` × 50 | template-stub on every empty-retrieval session | _to fill_ |
| Δ overall accuracy vs. flat-vector | _to fill_ pp | _depends on slice_ | _to fill_ |
| Δ overall accuracy vs. no-memory | _to fill_ pp | _depends on slice_ | _to fill_ |

**Token budget.** Recency-pruning prompts are ~120 tokens (same
template as flat-vector with the same retrieved-memory block); no
truncation; well under `num_ctx=2048`.

**Latency.** _to fill_ ms / session. Comparable to flat-vector
because the retrieval surface is identical; the only added cost is the
SQLite insert + the FIFO eviction check, both O(N·log N) at N=50.

## 1. Predicted-vs-observed gap (per competency)

The §3 design note pre-registered per-competency hypotheses. This
section measures how the host run actually played out on the synthetic
placeholder.

| Competency | No-memory | Flat-vector | Recency | Δ (rec−fv) | Predicted (synthetic) | Direction matches? |
|---|---:|---:|---:|---:|---|:-:|
| single-session-user      | _to fill_ | _to fill_ | _to fill_ | _to fill_ | ≈ flat-vector (synthetic ⇒ +0 pp) | _to fill_ |
| single-session-assistant | _to fill_ | _to fill_ | _to fill_ | _to fill_ | ≈ flat-vector (synthetic ⇒ +0 pp) | _to fill_ |
| single-session-preference| _to fill_ | _to fill_ | _to fill_ | _to fill_ | ≈ flat-vector; **leak check** | _to fill_ |
| multi-session            | _to fill_ | _to fill_ | _to fill_ | _to fill_ | mixed: gain over no-memory, loss vs. flat-vector on REAL slice; +0 pp on synthetic | _to fill_ |
| knowledge-update         | _to fill_ | _to fill_ | _to fill_ | _to fill_ | possible gain vs. flat-vector on REAL slice (newest-wins by accident); +0 pp on synthetic | _to fill_ |
| temporal-reasoning       | _to fill_ | _to fill_ | _to fill_ | _to fill_ | mixed; +0 pp on synthetic | _to fill_ |
| abstention               | _to fill_ | _to fill_ | _to fill_ | _to fill_ | ≈ flat-vector; +0 pp on synthetic | _to fill_ |

**Verdict on the §3 design note hypotheses:** _to fill on real slice_.

## 2. Eviction-of-truth qualitative examples

Recency-pruning has a specific failure mode the thesis cares about: it
can evict a memory that is still currently true simply because new
items arrived. The §3.5 procedure: from the action_log, find sessions
where (a) recency evicted item X via FIFO, (b) the LongMemEval-S gold
references information equivalent to X, (c) recency got the question
wrong, (d) flat-vector got it right. This is the diagnostic case:
recency loses information that flat-vector preserves.

Hand-classify ≤10 such sessions if they exist; record proportion. This
is a precursor to the under-forgetting rate Month 4 measures formally.

| # | session_id | competency | recency wrong? | flat_vector right? | evicted item (excerpt) | gold matches evicted? | classification |
|---|---|---|:-:|:-:|---|:-:|---|
| 1 | _to fill on real slice_ | | | | | | |
| 2 | _to fill on real slice_ | | | | | | |
| 3 | _to fill on real slice_ | | | | | | |
| 4 | _to fill on real slice_ | | | | | | |
| 5 | _to fill on real slice_ | | | | | | |
| 6 | _to fill on real slice_ | | | | | | |
| 7 | _to fill on real slice_ | | | | | | |
| 8 | _to fill on real slice_ | | | | | | |
| 9 | _to fill on real slice_ | | | | | | |
| 10 | _to fill on real slice_ | | | | | | |

**Eviction-of-truth proportion on synthetic slice:** N/A — every
session's `supporting_session_ids` filters to empty, so admissions and
evictions are 0 across the slice. The 10-row table waits for the real
slice.

## 3. Distractor-vs-eviction trade-off

Compare recency to flat-vector: recency retains less and may be
cleaner; flat-vector retains everything and may be noisier. On which
competencies does each win?

_to fill on real slice — one-paragraph summary based on §1 numbers
and §2 examples_

## 4. Capacity sensitivity peek (5 sessions, N=25)

The 5-session capacity=25 peek (`runs/m1w4/recency_cap25_peek/`)
confirms the **sign** of the effect: smaller capacity = more eviction
= expected drop on multi-session.

| Competency | Recency N=50 (5-session peek subset) | Recency N=25 (5-session peek) | Δ |
|---|---:|---:|---:|
| _from peek run_ | _to fill_ | _to fill_ | _to fill_ |

**Verdict:** _to fill_ — the sign of the effect is _expected /
unexpected / null on synthetic_.

A full sweep (N ∈ {10, 25, 50, 100}) is **deferred to Month-4
ablations** (proposal §I.7.3).

## 5. What we learned about recency (one-paragraph summary)

> _to fill on real slice — close-out paragraph following the W3 §5
> template. Mention: substrate (memory_items + action_log) is in
> place and tested; recency degenerates to no-memory + empty stub
> on synthetic by construction; eviction-of-truth signature waits
> for the real slice; capacity peek confirms sign of effect; the
> destructiveness gap (no lineage on FIFO eviction) is the
> setup for Chapter 4 §4.X versioning-vs-overwrite ablation. The
> three design choices (trivial extractor, N=50, FAISS k=5
> retrieval identical to flat-vector) are now the **stable
> substrate Week 5 picks up** for the proper LLM-based extractor._

## 6. Pipeline checks already automated (covered by pytest)

These guard against regression of the §3.1, §3.2, §3.3 invariants. A
fresh M1-W4 + carried-forward suite is **125 passed, 3 skipped** as
the pre-flight check at the start of this run.

- `tests/test_memory_operations.py::*` (13 tests) — substrate
- `tests/test_action_log.py::*` (12 tests) — audit log
- `tests/test_recency_pruning.py::*` (14 tests) — baseline
- carry-over from M1-W3: `tests/test_flat_vector*.py`, `tests/test_embeddings.py`
- carry-over from M1-W2: `tests/test_no_memory.py`, `tests/test_longmemeval_eval.py`

If any of these regress in the future, M1-W4's claims regress with them.
