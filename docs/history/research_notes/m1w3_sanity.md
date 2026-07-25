# M1-W3 sanity check — Baseline 2 (flat-vector memory)

**Run completed:** 2026-04-26 on host (laptop, Apple Silicon).
**Wall-clock:** 1969.9 s (~32.8 min) — well inside the §5.2 acceptance
budget of 7200 s (2 h).
**Configuration:** Ollama `gemma4:e4b`, flat-vector with k=5,
`sentence-transformers/all-MiniLM-L6-v2` embeddings (CPU), FAISS
`IndexFlatIP` over L2-normalized rows.

**Headline:** every check passes; the slice-level result is **Δ +0 pp
across every competency vs. M1-W2 no-memory** — exactly the synthetic-
placeholder-slice prediction registered in `NOTES/m1w3_design.md` §1.
Anti-leakage (current session never appears in retrieval) is verified
on all 50/50 sessions end-to-end.

This is the load-bearing step of M1-W3 (§3.5). The four checks below.

## 0. What the host run proves on the synthetic placeholder slice

Telemetry from `runs/m1w3/flat_vector/answers.jsonl` (50 sessions, all
fields validated programmatically):

| Property | Value | Expected | Pass? |
|---|---|---|:-:|
| `n_total` answers persisted | 50 | 50 | ✓ |
| sessions with `n_indexed=0` | 50 | 50 (every `supporting_session_ids` filters to empty) | ✓ |
| sessions with `n_retrieved=0` | 50 | 50 | ✓ |
| sessions where current session_id appears in `retrieval_session_ids` | **0** | **must be 0** (anti-leakage) | ✓ |
| `extras` keys present on every record | `embedder_model_id, k, n_indexed, n_retrieved, retrieval_scores, retrieval_session_ids, retrieval_turn_idxs, supporting_session_ids, unresolved_supporting_ids` | 9 fields | ✓ |
| RETRIEVED MEMORY block in rendered prompt | `[no relevant memory found]` × 50 | template-stub on every empty-retrieval session | ✓ |
| Δ overall accuracy vs. no-memory | +0.0 pp | +0.0 pp | ✓ |
| Wall-clock | 1969.9 s | < 7200 s | ✓ |

**Token budget.** Flat-vector prompts are ~120 tokens vs. no-memory's
~104 — a +16-token overhead consistent with the
`----- RETRIEVED MEMORY -----` header + `[no relevant memory found]`
stub line + the new section delimiter. No truncation; well under the
`num_ctx=2048` cap. Risk #7 in the task table closes.

**Latency.** ~3000–4500 ms / session for flat-vector vs. ~2400–2900 ms
for no-memory. The +600–1500 ms is consistent with the per-session
MiniLM encode of supporting-session turns (zero indexed turns means
zero forward passes, so the overhead is the encode of the QUERY only —
one ~50-token forward pass per session) plus the additional ~16-token
generation cost from the larger prompt. No anomaly.

A separate stress fixture in
`tests/test_flat_vector.py::test_retrieved_memory_block_contains_top_k_turns_by_cosine_similarity`
exercises the real cross-session retrieval path with
`supporting_session_ids` that span DIFFERENT sessions; it passes
end-to-end with `FakeEmbedder` and asserts that the rank-0 retrieved
turn is the planted target turn at similarity ≈ 1.0. This is the
unit-level evidence that retrieval will do the right thing once the
real LongMemEval-S file replaces the placeholder.

## 1. Predicted-vs-observed gap (per competency)

The §3.0 design note pre-registered these per-competency hypotheses;
this section measures how the host run actually played out on the
synthetic placeholder.

| Competency | No-memory (W2) | Flat-vector (W3) | Δ | Predicted (synthetic) | Direction matches? |
|---|---:|---:|---:|---|:-:|
| single-session-user      | 100.0% | 100.0% | +0.0 pp | ≈ no-memory (synthetic ⇒ +0 pp) | ✓ |
| single-session-assistant | 100.0% | 100.0% | +0.0 pp | ≈ no-memory (synthetic ⇒ +0 pp) | ✓ |
| single-session-preference| 100.0% | 100.0% | +0.0 pp | ≈ no-memory; **leak check** below | ✓ |
| multi-session            | 100.0% | 100.0% | +0.0 pp | substantial gain on REAL slice; +0 pp on synthetic | ✓ (synthetic) |
| knowledge-update         | 100.0% | 100.0% | +0.0 pp | substantial gain on REAL slice; +0 pp on synthetic | ✓ (synthetic) |
| temporal-reasoning       | 100.0% | 100.0% | +0.0 pp | mixed; modest gain on REAL slice; +0 pp on synthetic | ✓ (synthetic) |
| abstention               | 100.0% | 100.0% | +0.0 pp | ≈ no-memory; +0 pp on synthetic | ✓ |

**Verdict on the §5.4 acceptance criterion** (flat-vector ≥ no-memory
on at least one of {`multi-session`, `knowledge-update`}): on the
synthetic placeholder the criterion reads as equality at 100% — both
baselines saturate **by construction of the placeholder corpus**, not
by anything wrong with retrieval. The substantive form of §5.4 becomes
meaningful when the real LongMemEval-S file replaces
`data/longmemeval_s_synthetic.jsonl`; the design note already pre-
registers the predicted gain pattern (substantial on multi-session and
knowledge-update; ≈ 0 on single-session and abstention).

## 2. Five wins / five losses

`scripts/win_loss.py` over `runs/m1w2/no_memory/judgments.jsonl` and
`runs/m1w3/flat_vector/judgments.jsonl` returns:

```
| Competency               |  n | both-correct | new-only (gain) | ref-only (loss) | both-wrong |
| abstention               | 10 |           10 |               0 |               0 |          0 |
| knowledge-update         | 10 |           10 |               0 |               0 |          0 |
| multi-session            |  6 |            6 |               0 |               0 |          0 |
| single-session-assistant |  6 |            6 |               0 |               0 |          0 |
| single-session-preference|  6 |            6 |               0 |               0 |          0 |
| single-session-user      |  6 |            6 |               0 |               0 |          0 |
| temporal-reasoning       |  6 |            6 |               0 |               0 |          0 |
| **all**                  | 50 |           50 |               0 |               0 |          0 |
```

**Net = (new-only) − (ref-only) = 0 sessions across all competencies.**
Zero disagreements across the slice. The synthetic placeholder produces
identical predictions on both baselines because every flat-vector
retrieved-memory block is empty (`[no relevant memory found]`), so the
generator has the same input on both sides modulo the stub header. The
classical "5 wins / 5 losses" exercise is therefore vacuous on this
slice — there is nothing to read.

This section becomes substantive once the real LongMemEval-S file lands
and produces actual disagreements; the `scripts/win_loss.py` deliverable
+ `NOTES/m1w3_win_loss.md` automation are in place for that re-run.

## 3. Single-session-preference leakage check

| | no-memory | flat-vector | Δ |
|---|---:|---:|---:|
| single-session-preference accuracy | 100.0% | 100.0% | +0.0 pp |

**Verdict: no leak observed.** Two pieces of evidence:

1. End-to-end telemetry: every `single-session-preference` answer in
   `runs/m1w3/flat_vector/answers.jsonl` has `n_indexed=0` and
   `n_retrieved=0`, and the rendered prompt's RETRIEVED MEMORY block
   reads `[no relevant memory found]`. There is nowhere for a leak to
   come from.
2. Unit-level: `tests/test_flat_vector.py::`
   `test_no_current_session_leakage_in_retrieved_block` enforces this
   invariant on a stress fixture that explicitly includes the current
   session_id in `supporting_session_ids`.

If the real-LME-S re-run shows `single-session-preference` jumping
above no-memory while every other single-session row stays flat, that
is the leak signature §3.5 calls out — re-run this check at that point.

## 4. Distractor breakdown — 10 disagreement examples (precursor to SMRR)

On the synthetic placeholder slice, **the disagreement set is empty
(0/50 sessions)** so there are no examples to classify in the
{a, b, c, d} taxonomy. Recording this fact instead of papering over it:

| | Count |
|---|---:|
| (a) genuine retrieval win | — |
| (b) retrieval irrelevant, generation got it anyway | — |
| (c) retrieval distracted generation | — |
| (d) judge disagreement | — |
| **Total disagreements** | **0** |

**Distractor proportion (c) on synthetic slice:** N/A.

Re-running `scripts/finalize_m1w3.sh` after
`data/longmemeval_s_synthetic.jsonl` is replaced with a real
LongMemEval-S release file produces the data this section needs. The
pre-registered M1-W3 finding (per `NOTES/m1w3_design.md` §3) is that
`(c)` clusters on `knowledge-update`: flat-vector retrieves the OLD
fact as confidently as the new one because the store has no
`status='active'` filter. That observation is the bridge to Month 4's
formal SMRR metric and to the controller's existence argument.

The ten-row table is left in place (with `_to fill on real slice_`
markers) so the same `m1w3_sanity.md` doubles as the analysis surface
for the real-slice re-run.

| # | session_id | competency | flat_vector correct? | no_memory correct? | rank-0 turn (excerpt) | classification (a / b / c / d) |
|---|---|---|:-:|:-:|---|---|
| 1 | _to fill on real slice_ | | | | | |
| 2 | _to fill on real slice_ | | | | | |
| 3 | _to fill on real slice_ | | | | | |
| 4 | _to fill on real slice_ | | | | | |
| 5 | _to fill on real slice_ | | | | | |
| 6 | _to fill on real slice_ | | | | | |
| 7 | _to fill on real slice_ | | | | | |
| 8 | _to fill on real slice_ | | | | | |
| 9 | _to fill on real slice_ | | | | | |
| 10 | _to fill on real slice_ | | | | | |

## 5. What we learned about retrieval (one-paragraph summary)

> The flat-vector baseline runs end-to-end on the 50-session synthetic
> placeholder slice in 1969.9 s (~33 min, well under the 2-hour
> acceptance budget) and reads Δ +0.0 pp across every competency vs.
> M1-W2 no-memory. This is exactly the prediction registered in the
> design note: every session's `supporting_session_ids` reduces to the
> current session, which the baseline excludes per
> `m1w3_design.md` §2.5, so retrieval has nothing to retrieve and the
> RETRIEVED MEMORY block reads `[no relevant memory found]` on all 50
> sessions. The anti-leakage contract holds end-to-end (0/50 sessions
> show the current `session_id` in `retrieval_session_ids`); the
> per-session telemetry persists all 9 fields the §3.5 sanity-check
> protocol depends on; the cross-session retrieval path is exercised
> at unit-test level on a stress fixture that plants a target turn in
> a prior session and asserts rank-0 retrieval at similarity ≈ 1.0.
> Both baselines reach 100% on this slice **by construction of the
> placeholder corpus** (every gold appears verbatim in the visible
> dialog), so the slice cannot distinguish them — that distinction
> waits for the real LongMemEval-S release file. The pipeline is
> validated; the substantive multi-session / knowledge-update gain
> and the distractor-retrieval losses that motivate the M3 controller
> appear with no code change required, only a `scripts/build_slice.py`
> rebuild and a re-run of `scripts/finalize_m1w3.sh`. The four design
> choices (MiniLM-L6-v2, role-tagged turn-level chunking, k=5,
> per-question reset with current-session exclusion) and the
> `extras.retrieval_*` telemetry are now the **stable substrate Week 4
> picks up** for the recency-pruning baseline + `action_log` writer
> that closes Gate G1.

## 6. Pipeline checks already automated (covered by pytest)

These guard against regression of the §3.4 invariants (analogous to
M1-W2's §7). The full M1-W3 + carried-forward suite was **58 passed,
2 skipped** as the pre-flight check at the start of this run (the 2
skipped are the host-only MiniLM smoke tests, gated by
`ASK_RUN_MINILM_SMOKE=1` to defuse the Apple-Silicon libomp segfault
documented in `m1w3_design.md` §5b).

- `tests/test_embeddings.py::test_fake_embedder_rows_are_l2_normalized`
- `tests/test_embeddings.py::test_turn_embedder_known_dim_resolves_without_load`
- `tests/test_embeddings.py::test_turn_embedder_real_minilm_smoke` (gated)
- `tests/test_flat_vector_store.py::test_search_for_own_text_returns_self_at_top1`
- `tests/test_flat_vector_store.py::test_clear_returns_search_to_empty`
- `tests/test_flat_vector_store.py::test_dim_mismatch_raises_on_add`
- `tests/test_flat_vector.py::test_no_current_session_leakage_in_retrieved_block`
- `tests/test_flat_vector.py::test_degenerates_to_no_memory_when_supporting_is_empty`
- `tests/test_flat_vector.py::test_per_question_reset_does_not_leak_across_questions`
- `tests/test_flat_vector.py::test_determinism_same_session_same_seed`
- `tests/test_flat_vector.py::test_retrieved_memory_block_contains_top_k_turns_by_cosine_similarity`

If any of these regress in the future, M1-W3's claims regress with them.
