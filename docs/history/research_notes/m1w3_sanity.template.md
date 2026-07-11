# M1-W3 sanity check — Baseline 2 (flat-vector memory)

**Run completed:** ${RUN_TIMESTAMP_UTC} (UTC).
**Wall-clock:** ${RUN_WALL_SECONDS}s on the host (Ollama `${RUN_MODEL_TAG}`,
flat-vector with k=${RUN_K}, MiniLM-L6-v2 embeddings, FAISS `IndexFlatIP`).
**Acceptance criterion:** § 5.2 requires < 7200 s (2 h); see top of file
for actual.

This is the load-bearing step of M1-W3 (§3.5). Three checks before the
flat-vector numbers are reliable enough to merge into the running
two-baseline table:

  1. **Predicted-vs-observed gap** on `multi-session` and
     `knowledge-update` (§1 below).
  2. **Read 5 wins / 5 losses** where flat-vector and no-memory
     disagree (§2). Each must be readable as either a genuine
     retrieval win or a documented failure mode.
  3. **Single-session-preference leakage check** (§3) — flat-vector
     should NOT substantially beat no-memory here. If it does, the
     prompt is leaking the gold answer.

Plus the §4 distractor classification: a hand-built precursor to the
**stale-memory retrieval rate (SMRR)** that Month 4 measures formally.
Getting a feel for it now sharpens the M4 metric.

## 1. Predicted-vs-observed gap (per competency)

The §3.0 design note pre-registered these per-competency hypotheses;
this section measures how the host run actually played out.

| Competency | No-memory (W2) | Flat-vector (W3) | Δ | Predicted | Observed direction matches? |
|---|---:|---:|---:|---|---|
| single-session-user | _to fill_ | _to fill_ | _to fill_ | ≈ no-memory or slight drop | _yes / no_ |
| single-session-assistant | _to fill_ | _to fill_ | _to fill_ | ≈ no-memory or slight drop | _yes / no_ |
| single-session-preference | _to fill_ | _to fill_ | _to fill_ | ≈ no-memory; **leak check** | _yes / no_ |
| multi-session | _to fill_ | _to fill_ | _to fill_ | substantial gain | _yes / no_ |
| knowledge-update | _to fill_ | _to fill_ | _to fill_ | substantial gain (with distractor losses) | _yes / no_ |
| temporal-reasoning | _to fill_ | _to fill_ | _to fill_ | mixed; modest gain | _yes / no_ |
| abstention | _to fill_ | _to fill_ | _to fill_ | ≈ no-memory or slight drop | _yes / no_ |

**Verdict on the §3.5 acceptance criterion (§5.4 of the task spec):**
flat-vector ≥ no-memory on at least one of {`multi-session`,
`knowledge-update`}? **_to fill: yes / no_**.

If **no**: do not paper over it. Debug retrieval before merging the
table. Common causes (in decreasing order of likelihood):

  1. The slice is the synthetic placeholder, not real LongMemEval-S
     (in which case Δ = 0 across the board is **expected** and
     documented in `NOTES/m1w3_design.md` §1; this is not a bug).
  2. L2-normalization broke and cosine became meaningless — check
     row norms in a debug session.
  3. Retrieval is reading from the wrong session set — check the
     `extras.retrieval_session_ids` field on a few answers; current
     session must NOT appear.
  4. Prompt template is hiding the retrieved block from the LLM —
     dump `raw_prompt` for a multi-session question.

## 2. Five wins / five losses (read this section)

After the host run, fill this from `runs/m1w3/flat_vector/judgments.jsonl`
crossed with `runs/m1w2/no_memory/judgments.jsonl`. The disagreement
session IDs are listed in `NOTES/m1w3_win_loss.md` per competency.

```bash
# Generate the disagreement list (same script the runner already ran):
python scripts/win_loss.py \
    --ref runs/m1w2/no_memory/judgments.jsonl \
    --new runs/m1w3/flat_vector/judgments.jsonl \
    --ref-name no_memory --new-name flat_vector

# Read a specific session's full grade record:
jq -c 'select(.session_id == "lme-s-XXX")' \
    runs/m1w3/flat_vector/judgments.jsonl

# Read the corresponding answer + retrieval telemetry:
jq -c 'select(.session_id == "lme-s-XXX")' \
    runs/m1w3/flat_vector/answers.jsonl | jq '.extras'
```

### Five wins (flat-vector correct, no-memory wrong)

For each: quote the gold, the prediction, and the rank-0 retrieved turn.
The prediction should obviously trace back to a retrieved turn.

> 1. session `lme-s-XXX` [competency]:
>    * gold: ...
>    * predicted: ...
>    * top-1 retrieval: session `lme-s-YYY`, turn `Z`, score `0.NN`,
>      content `"..."`
>    * verdict: _genuine retrieval win_

> 2. _to fill_

> 3. _to fill_

> 4. _to fill_

> 5. _to fill_

### Five losses (flat-vector wrong, no-memory correct)

For each: quote the gold, the prediction, and the rank-0 retrieved turn.
The expected pattern is **a distractor at rank 0** — a turn semantically
similar to the question but not actually answer-bearing. This is the
central failure mode of flat-vector and motivates the controller.

> 1. _to fill_

> 2. _to fill_

> 3. _to fill_

> 4. _to fill_

> 5. _to fill_

## 3. Single-session-preference leakage check

Flat-vector should not substantially beat no-memory on
`single-session-preference` because the answer is in the current
session — retrieval can only add noise. A large gain here means the
prompt is leaking the gold answer somewhere.

| | no-memory | flat-vector | Δ |
|---|---:|---:|---:|
| single-session-preference accuracy | _to fill_ | _to fill_ | _to fill_ |

**Verdict:** _no leak observed / leak suspected, debug ..._

If a leak is suspected: dump `raw_prompt` for one
`single-session-preference` answer and confirm the `RETRIEVED MEMORY`
section is empty (per design note §2.5, supporting_session_ids minus
self ⇒ empty for any single-session question).

## 4. Distractor breakdown — 10 disagreement examples (precursor to SMRR)

Pick 10 sessions where flat-vector and no-memory disagree (5 wins,
5 losses, or all 10 from the larger cell if asymmetric). For each,
classify into one of:

  a. **Genuine retrieval win** — the rank-0 retrieved turn is
     answer-bearing and the prediction quotes / paraphrases it.
  b. **Retrieval irrelevant, generation got it anyway** — rank-0
     is a distractor but the prediction is still correct.
  c. **Retrieval distracted generation** — rank-0 is a distractor
     and the prediction follows it down the wrong path.
  d. **Judge disagreement** — both predictions are arguably correct;
     the judge made a different call.

The expected M1-W3 finding (per `NOTES/m1w3_design.md` §3) is that
`(c)` clusters on `knowledge-update` — flat-vector retrieves the OLD
fact as confidently as the new one because the store has no
`status='active'` filter.

| # | session_id | competency | flat_vector correct? | no_memory correct? | rank-0 turn (excerpt) | classification (a / b / c / d) |
|---|---|---|:-:|:-:|---|---|
| 1 | _to fill_ | | | | | |
| 2 | _to fill_ | | | | | |
| 3 | _to fill_ | | | | | |
| 4 | _to fill_ | | | | | |
| 5 | _to fill_ | | | | | |
| 6 | _to fill_ | | | | | |
| 7 | _to fill_ | | | | | |
| 8 | _to fill_ | | | | | |
| 9 | _to fill_ | | | | | |
| 10 | _to fill_ | | | | | |

**Distractor proportion:** (c-count) / 10 = _to fill_

This proportion is the hand-built foreshadow of the formal SMRR metric
in Month 4. Record it now so the M4 metric has a concrete target to
beat: the controller's status='active' filter is the upgrade path that
should drive this proportion toward zero on `knowledge-update`.

## 5. What we learned about retrieval (one-paragraph summary)

> _To fill after the run, in 4–6 sentences. Quote the predicted-vs-
> observed gap on multi-session and knowledge-update specifically.
> Note the distractor proportion. Comment on whether this is the
> evidence that motivates the M3 controller, or whether something
> in the pipeline still needs fixing first._

## 6. Pipeline checks already automated (covered by pytest)

These guard against regression of the §3.4 invariants (analogous to
M1-W2's §7):

- `tests/test_embeddings.py::test_fake_embedder_rows_are_l2_normalized`
- `tests/test_embeddings.py::test_turn_embedder_real_minilm_smoke` (host only)
- `tests/test_flat_vector_store.py::test_search_for_own_text_returns_self_at_top1`
- `tests/test_flat_vector_store.py::test_clear_returns_search_to_empty`
- `tests/test_flat_vector.py::test_no_current_session_leakage_in_retrieved_block`
- `tests/test_flat_vector.py::test_degenerates_to_no_memory_when_supporting_is_empty`
- `tests/test_flat_vector.py::test_per_question_reset_does_not_leak_across_questions`
- `tests/test_flat_vector.py::test_determinism_same_session_same_seed`

If any of these regress in the future, M1-W3's claims regress with them.
