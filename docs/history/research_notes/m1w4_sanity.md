# M1-W4 sanity check — Baseline 3 (recency-pruning)

**Run completed:** 2026-04-27 (host run via `bash scripts/finalize_m1w4.sh`).
**Wall-clock:** 1586.5s (~26.4 min) for the recency baseline alone;
1683.4s + 1792.6s + 1586.5s = 5062.5s (~84.4 min) for all three baselines
on the slice; +114.7s for the 5-session capacity=25 peek. All under
the §6 acceptance budget of 7200s for the recency run.
**Configuration:** Ollama `gemma4:e4b`, recency-pruning with
capacity N=50, k=5, `sentence-transformers/all-MiniLM-L6-v2`
embeddings (CPU), FAISS `IndexFlatIP` over L2-normalized rows.
Trivial extractor (every user turn → one episodic_fact, conf=1.0).

**Headline:** every check passes; the slice-level result is **Δ +0 pp
across every competency vs. M1-W3 flat-vector and M1-W2 no-memory** —
exactly the synthetic-placeholder-slice prediction registered in
`NOTES/m1w4_design.md` §3. Anti-leakage (current session never
appears in retrieval) is verified on all 50/50 sessions end-to-end.

This is the load-bearing step of M1-W4 (§3.5). Six sections.

## 0. What the host run proved on the synthetic placeholder slice

Telemetry from `runs/m1w4/recency/answers.jsonl` (50 sessions, all
fields validated programmatically):

| Property | Measured value | Expected | Pass? |
|---|---|---|:-:|
| `n_total` answers persisted | 50 | 50 | ✓ |
| sessions with `n_admitted=0` | 50 | 50 (every `supporting_session_ids` filters to empty) | ✓ |
| sessions with `n_active=0` | 50 | 50 | ✓ |
| sessions with `n_evicted=0` | 50 | 50 (no admissions → no evictions) | ✓ |
| sessions where current session_id appears in `retrieval_session_ids` | **0** | **must be 0** (anti-leakage carry-over from W3) | ✓ |
| `extras` keys present on every record | 13 fields (`capacity, embedder_model_id, k, n_active, n_admitted, n_evicted, n_retrieved, retrieval_memory_ids, retrieval_scores, retrieval_session_ids, retrieval_turn_idxs, supporting_session_ids, unresolved_supporting_ids`) | 13 fields | ✓ |
| RETRIEVED MEMORY block in rendered prompt | `[no relevant memory found]` × 50 | template-stub on every empty-retrieval session | ✓ |
| Δ overall accuracy vs. flat-vector (W4 rerun) | +0.0 pp | +0.0 pp on synthetic | ✓ |
| Δ overall accuracy vs. no-memory (W4 rerun) | +0.0 pp | +0.0 pp on synthetic | ✓ |
| `action_log.jsonl` line count | **0** | 0 (no admit, no evict events on this slice) | ✓ |
| Wall-clock | 1586.5s | < 7200s | ✓ |

**Token budget.** Recency prompts are ~120 tokens (same template as
flat-vector with the identical `[no relevant memory found]` stub);
no truncation; well under `gemma4:e4b`'s 2048 `num_ctx` cap.

**Latency.** 2480–3108 ms / session for recency. **Faster than
flat-vector** (2802–4665 ms / session): on this slice `n_admitted=0`
means recency does zero MiniLM forward passes (the flat-vector
baseline still embeds the question to query the empty index;
recency skips the embed step entirely when the active set is
empty). On the real slice the picture inverts as admissions kick in.

A separate stress fixture in
`tests/test_recency_pruning.py::test_capacity_invariant_inserting_more_items_than_capacity`
(100 items, capacity=50) exercises the FIFO admit/evict path and
asserts `n_active=50, n_evicted=50` end-to-end. This is the
unit-level evidence that capacity + FIFO will do the right thing
once the real LongMemEval-S file replaces the placeholder.

## 1. Predicted-vs-observed gap (per competency)

The §3 design note pre-registered per-competency hypotheses; this
section measures how the host run actually played out on the
synthetic placeholder.

| Competency | No-memory (W4 rerun) | Flat-vector (W4 rerun) | Recency (W4) | Δ (rec−fv) | Predicted (synthetic) | Direction matches? |
|---|---:|---:|---:|---:|---|:-:|
| single-session-user      | 100.0% | 100.0% | 100.0% | +0.0 pp | ≈ flat-vector (synthetic ⇒ +0 pp) | ✓ |
| single-session-assistant | 100.0% | 100.0% | 100.0% | +0.0 pp | ≈ flat-vector (synthetic ⇒ +0 pp) | ✓ |
| single-session-preference| 100.0% | 100.0% | 100.0% | +0.0 pp | ≈ flat-vector; **leak check** below | ✓ |
| multi-session            | 100.0% | 100.0% | 100.0% | +0.0 pp | mixed: gain over no-memory, **loss vs. flat-vector** on REAL slice; +0 pp on synthetic | ✓ (synthetic) |
| knowledge-update         | 100.0% | 100.0% | 100.0% | +0.0 pp | **possible *gain* vs. flat-vector** on REAL slice (newest-wins by accident); +0 pp on synthetic | ✓ (synthetic) |
| temporal-reasoning       | 100.0% | 100.0% | 100.0% | +0.0 pp | mixed; +0 pp on synthetic | ✓ (synthetic) |
| abstention               | 100.0% | 100.0% | 100.0% | +0.0 pp | ≈ flat-vector; +0 pp on synthetic | ✓ |

**Verdict on the §3 design note hypotheses on the synthetic slice:**
all rows read as equality at 100% — both flat-vector and recency
saturate **by construction of the placeholder corpus**, not by
anything wrong with the substrate. The substantive form of the
hypotheses (knowledge-update gain via newest-wins; multi-session
loss via eviction-of-truth) becomes meaningful when the real
LongMemEval-S file replaces `data/longmemeval_s_synthetic.jsonl`;
the design note pre-registers the predicted gain pattern.

## 2. Eviction-of-truth qualitative examples (precursor to under-forgetting rate)

The §3.5 procedure: from `runs/m1w4/recency/action_log.jsonl`, find
sessions where (a) recency evicted item X via FIFO, (b) the
LongMemEval-S gold answer references information equivalent to X,
(c) recency got the question wrong, (d) flat-vector got it right.
This is the diagnostic case: recency loses information that
flat-vector preserves.

**On this slice the action_log is empty (0 lines) and recency vs.
flat-vector / vs. no-memory disagreement set is empty (50 both-
correct, 0 disagreements).** Recording this fact instead of
papering over it.

| | Count |
|---|---:|
| Sessions where recency evicted ≥ 1 item | 0 |
| Sessions in the (recency-wrong, flat-vector-right) cell | 0 |
| Eviction-of-truth examples on the synthetic slice | **0** |

The 10-row table is left in place (with `_to fill on real slice_`
markers) so this same `m1w4_sanity.md` doubles as the analysis
surface for the real-slice re-run. These 10 examples are the seed
material for the Discussion-chapter informal failure-mode analysis
(proposal §II.4 transient capture, silent revision); they will be
gold for Chapter 6.

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

## 3. Distractor-vs-eviction trade-off (one-paragraph summary)

> On the synthetic slice the trade-off is degenerate: both flat-
> vector and recency render the empty-stub
> `[no relevant memory found]` block on every session, so neither
> distracts (flat-vector retrieves nothing irrelevant) and neither
> evicts a true fact (recency admits nothing). The two failure
> modes are anti-correlated and both register zero. The substantive
> form of the trade-off — flat-vector retains everything, paying a
> distractor-retrieval rate proportional to the irrelevant-content
> density of `supporting_session_ids`; recency-pruning trades that
> distractor rate for an eviction-of-truth rate proportional to the
> FIFO horizon relative to the gold-relevant horizon — will read
> off the real-slice re-run. Per the M2-W5 plan, that re-run lands
> at the start of Month 2 with no code change required.

## 4. Capacity sensitivity peek (5 sessions, N=25)

The 5-session capacity=25 peek (`runs/m1w4/recency_cap25_peek/`,
wall-clock 114.7s) confirms the **null sign** of the effect on the
synthetic slice — exactly as predicted in `m1w4_design.md` §1b.

| Competency (5-session subset) | Recency N=50 | Recency N=25 | Δ |
|---|---:|---:|---:|
| single-session-assistant (1 / 5) | 100.0% | 100.0% | +0.0 pp |
| knowledge-update (1 / 5) | 100.0% | 100.0% | +0.0 pp |
| abstention (1 / 5) | 100.0% | 100.0% | +0.0 pp |
| single-session-preference (2 / 5) | 100.0% | 100.0% | +0.0 pp |
| **5-session overall** | **100.0%** | **100.0%** | **+0.0 pp** |

**Verdict:** **null** — no `supporting_session_ids` resolves to
non-empty on this slice, so neither N=50 nor N=25 admits any items,
neither evicts any items, and the per-competency accuracy is
identical at 100% across both capacities. The sign-of-effect check
waits for the real slice; on the synthetic slice the null result is
the correct, documented behavior.

A full sweep (N ∈ {10, 25, 50, 100}) is **deferred to Month-4
ablations** (proposal §I.7.3). The 5-session peek is purely a sanity
check, not the ablation.

## 5. What we learned about recency (one-paragraph summary)

> The recency-pruning baseline ran end-to-end on the 50-session
> synthetic placeholder slice in 1586.5s (~26 min, well under the
> 2-hour acceptance budget) and reads Δ +0.0 pp across every
> competency vs. M1-W3 flat-vector and vs. M1-W2 no-memory. This
> is exactly the prediction registered in the design note: every
> session's `supporting_session_ids` filters to empty after the W3
> §2.5 anti-leak rule, so the trivial extractor admits zero items,
> the FIFO queue stays empty, no evictions fire, the action_log
> is empty (0 lines), the retrieval index is empty, and both
> `.j2` templates emit the identical `[no relevant memory found]`
> stub. The recency rendered prompt is byte-equal to flat-vector's,
> the answers and grades are byte-equal too, and the anti-leakage
> contract holds end-to-end (0/50 sessions show the current
> `session_id` in `retrieval_session_ids`). The substrate
> `memory_items` + `action_log` is **load-bearing for the rest of
> the thesis** — it is the data structure the controller, the
> MGP-6 evaluation, and the qualitative analysis live in. The
> unit-test suite (`tests/test_memory_operations.py`,
> `tests/test_action_log.py`,
> `tests/test_recency_pruning.py`, 39 tests in total, all green;
> 125 passed sandbox-side and 100 passed host-side at the
> finalize-script pre-flight) covers (a) atomic supersede, (b)
> retrieve-active-only filter, (c) lineage-walk for the
> controller, (d) FIFO destructiveness for recency, (e) action_log
> round-trip / schema-rejection / crash-safety, (f) capacity
> invariant, (g) FIFO discipline, (h) determinism. The
> destructiveness gap (FIFO eviction destroys lineage; the
> controller's `supersede` primitive preserves it via
> `supersedes_id` chains) is now in code and covered by tests; the
> host run on the real slice will turn the qualitative
> eviction-of-truth signature into a count, and Month 4 will turn
> that count into the under-forgetting rate the thesis cares
> about. The three Week-4 design choices (trivial extractor;
> capacity N=50; identical retrieval to flat-vector) are the
> **stable substrate Week 5 picks up** for the proper LLM-based
> extractor.

## 6. Pipeline checks already automated (covered by pytest)

These guard against regression of the §3.1, §3.2, §3.3 invariants.

- Sandbox-side: **125 passed, 3 skipped** (M1-W4 + carried-forward).
- Host-side pre-flight (inside `scripts/finalize_m1w4.sh`):
  **100 passed, 2 skipped** (subset that finalize_m1w4.sh runs;
  the host-only Ollama smokes are separately gated).

- `tests/test_memory_operations.py` (13 tests):
  insert, supersede atomicity (forced exception), double-supersede
  loud failure, retrieve-active-only, type filter, lineage
  three-step chain, get_by_id regardless of status, supersede_evict
  destructiveness contract, double-evict.
- `tests/test_action_log.py` (12 tests):
  valid-entry round-trip, out-of-range feature rejection, unknown
  action rejection, N-entry round-trip with W4 fields, schema-
  rejection-does-not-write, baseline-allow-list, writer-baseline-
  override, crash-safety partial-file-parseable, mode='w' truncate,
  mode='a' append, pre-W4 entries still valid, supersede-with-null-
  resulting-id.
- `tests/test_recency_pruning.py` (14 tests):
  trivial extractor (user turns only, provenance), prompt-slot
  rendering, system-prompt parity, capacity invariant
  (over/under), FIFO discipline (action_log shape), action_log
  shape (Keep+Supersede mix), determinism, anti-leakage,
  degenerate-to-no-memory, per-question reset, capacity / k
  validation.
- carry-over from M1-W3 (`tests/test_flat_vector*.py`,
  `tests/test_embeddings.py`).
- carry-over from M1-W2 (`tests/test_no_memory.py`,
  `tests/test_longmemeval_eval.py`).

If any of these regress in the future, M1-W4's claims regress with
them.
