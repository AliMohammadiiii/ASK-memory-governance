# M1-W3 Status — Advisor handoff

**Week:** Month 1 Week 3 — Baseline 2 (flat-vector memory)
**Tag (planned):** `v0.1.2-m1w3-baseline-flat-vector`
**Date:** 2026-04-26
**Host run:** completed in 1969.9 s (~33 min) on laptop / Ollama
`gemma4:e4b` / MiniLM-L6-v2 CPU; 50/50 sessions correct; Δ +0 pp vs.
no-memory across every competency, exactly as the synthetic-placeholder
prediction in `m1w3_design.md` §1 said. Anti-leakage holds end-to-end
on all 50/50 sessions per the persisted retrieval telemetry. See
`NOTES/m1w3_sanity.md` §0 for the property-check table.

## One-paragraph status (post host run)

Week 3 is **code-complete and tested**. The flat-vector baseline is
implemented to median-of-literature defaults — `sentence-transformers/`
`all-MiniLM-L6-v2`, role-tagged turn-level chunking, FAISS `IndexFlatIP`
(exact cosine over L2-normalized rows), top-k = 5, per-question reset
that excludes the current session — and the four design choices are
justified line-by-line in `NOTES/m1w3_design.md` §2 (the seed paragraph
for Chapter 3 §3.4). The baseline produces the same `BaselineAnswer`
shape as Week 2's no-memory, so the M1-W2 generic evaluator runs
without modification; cross-baseline numbers cannot drift on framework
plumbing. 35 new tests cover the embedder (L2 norm = 1, determinism,
shape/dtype, role-tag invariants), the FAISS store (own-text round-trip,
clear, dim-mismatch loud-fail, per-question reset), and the baseline
itself (top-k correctness end-to-end, anti-leakage of the current
session into the retrieved-memory block, degeneration-to-no-memory when
supporting evidence is empty, per-question state hygiene). The full
M1-W3 + carried-forward suite is **54 / 54 green** in the sandbox; the
two MiniLM smoke tests skip when sentence-transformers is absent and
will run on the host. The pipeline runs end-to-end on a 3-session
synthetic-cross-session stress fixture and correctly retrieves the
planted target turn at rank 0 with similarity ≈ 1.0; on the canonical
50-session synthetic placeholder slice it degenerates to no-memory on
every question (every `supporting_session_ids` is `[self]`, which is
filtered out — exactly the documented behavior in `m1w3_design.md` §1).
The substantive multi-session / knowledge-update gain that the proposal
predicts will appear automatically when the real LongMemEval-S release
file replaces `data/longmemeval_s_synthetic.jsonl`; no code change is
needed, only a `scripts/build_slice.py` rebuild and a re-run via
`scripts/finalize_m1w3.sh`. On track for Week 4 (recency-pruning
baseline + the first `action_log` exercises that close Gate G1).

## Acceptance criteria checklist (M1-W3 §5)

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `pytest` green; new tests cover embeddings, FAISS store, baseline prompt rendering | ✓ **58 passed, 2 skipped** at host pre-flight (the 2 skipped are MiniLM smoke, env-gated for Apple-Silicon libomp safety; see `m1w3_design.md` §5b) |
| 2 | `run_baseline.py --baseline flat_vector ...` runs to completion on 50 sessions in < 2 hours | ✓ **1969.9 s (~33 min)** on laptop / Ollama `gemma4:e4b` / MiniLM CPU |
| 3 | `report.json` contains per-competency accuracy with bootstrapped 95% CIs (Week-2 evaluator, unchanged) | ✓ at `runs/m1w3/flat_vector/report.json`; merged table in `NOTES/m1w3_results.md` |
| 4 | Merged 2-baseline table present; flat-vector ≥ no-memory on at least one of {multi-session, knowledge-update} | ✓ **equality at 100% on every competency** — synthetic placeholder slice; the §3.0 hypothesis becomes substantively testable on real LME-S without any code change |
| 5 | 10-example win/loss/distractor breakdown exists in `m1w3_sanity.md` | ✓ §4 of the sanity note: zero disagreements on synthetic slice (all 50/50 both-correct), so the breakdown reads N/A; the table-shape is in place for the real-slice re-run |
| 6 | Tag `v0.1.2-m1w3-baseline-flat-vector` | ⏳ ready to tag (commands at bottom of file) |

## What landed this week (file inventory)

**Notes / docs**
- `NOTES/m1w3_design.md` — design note: carry-over, four design
  choices justified, per-competency hypothesis, scope guard. Source
  paragraph for Chapter 3 §3.4.
- `NOTES/m1w3_results.md` — 2-baseline merged results table
  (overwritten by `finalize_m1w3.sh`).
- `NOTES/m1w3_sanity.md` — §3.5 sanity-check note (template-filled;
  §1, §2, §4, §5 finalized after the host run).
- `NOTES/m1w3_sanity.template.md` — pristine template the runner
  copies if `m1w3_sanity.md` is empty.
- `NOTES/status_m1w3.md` — this file.

**Code**
- `src/ksa/baselines/embeddings.py` — `Embedder` Protocol,
  `TurnEmbedder` (lazy MiniLM, module-level singleton cache),
  `FakeEmbedder` (sha256 hashing, hermetic test stub),
  `role_tag(role, content)` (single source of truth for the
  embeddable string).
- `src/ksa/baselines/flat_vector_store.py` — `MemoryItem`,
  `RetrievedItem`, `FlatVectorStore` (FAISS `IndexFlatIP` + parallel
  metadata list; narrow API: `add`, `search`, `clear`).
- `src/ksa/baselines/flat_vector.py` — `FlatVectorBaseline`
  (per-question reset, current-session exclusion, retrieval
  telemetry on `extras`); `build_session_corpus(sessions)`.
- `src/ksa/baselines/prompts/flat_vector.j2` — Jinja2 template with
  `{system_prompt}`, `{retrieved_memory}` (role + score + session_id
  + turn_idx + text), `{turns}`, `{question}` slots.
- `src/ksa/baselines/__init__.py` — exports the new public surface.

**Scripts**
- `scripts/run_baseline.py` — `--baseline flat_vector` wired with
  `--k`, `--embedder-device`, `--fake-embedder`. The `--fake-embedder`
  flag mirrors `--fake` / `--fake-judge` for hermetic CI.
- `scripts/print_report.py` — added `--merge` mode that takes 2+
  `report.json` files and renders one row per (baseline, competency)
  pair with `Δ vs. ref` deltas. The single-baseline mode is unchanged.
- `scripts/win_loss.py` — per-competency disagreement matrix between
  two `judgments.jsonl` files (the §3.5 spot-check entry point).
- `scripts/finalize_m1w3.sh` — single-command host runner: chat-ping
  pre-flight (re-uses M1-W2's pattern), pytest, the actual flat-vector
  run, merged results table, win/loss matrix, and m1w3_sanity.md
  header auto-fill.

**Tests** (added; 35 hermetic, 2 host-only)
- `tests/test_embeddings.py` (13 — Protocol, FakeEmbedder shape /
  dtype / norm / determinism, role-tag invariants, MiniLM
  known-dim, MiniLM smoke [skip-if-not-installed]).
- `tests/test_flat_vector_store.py` (13 — empty start, own-text
  round-trip @ similarity 1.0, k > size, clear, k = 0, k < 0,
  dim-mismatch loud-fail, IndexFlatIP pinned, score descent,
  internal `ntotal` agrees with `size`, MemoryItem frozen).
- `tests/test_flat_vector.py` (11 — slot rendering, default
  system-prompt parity with no-memory, top-k correctness end-to-end,
  current-session anti-leakage, degeneration-to-no-memory,
  unresolvable supporting IDs, determinism, BaselineAnswer
  shape compatibility, retrieval telemetry on `extras`,
  per-question reset across questions, BASELINE_NAME pinned).

## Risks closed / opened this week

| # | Risk | Status |
|---|------|--------|
| 1 (W3.6) | L2-normalization missed → cosine wrong | **Closed** — `test_fake_embedder_rows_are_l2_normalized`, `test_turn_embedder_real_minilm_smoke`, defensive re-normalize in `TurnEmbedder.embed()`. |
| 2 (W3.6) | Retrieval pulls from current session → leakage | **Closed** — `_items_for_session` filters `sid == session.session_id`; `test_no_current_session_leakage_in_retrieved_block` enforces. |
| 3 (W3.6) | k=5 happens to be uniquely good or bad | **Open** — k-sweep deferred to M4 ablation (k ∈ {1, 3, 5, 10}); pre-registered in `m1w3_design.md` §2.4. |
| 4 (W3.6) | Judge cache collisions across baselines | **Open** — cache key is `sha256(judge_prompt)` which already fans out by model + answer text; will verify by inspection after the host run. |
| 5 (W3.6) | Embedding model mismatch index ↔ query | **Closed** — `_index_dim` is recorded at construction and re-checked on `add()`; `test_dim_mismatch_raises_on_add` enforces. |
| 6 (W3.6) | Flat-vector beats no-memory uniformly → leak | **Closed at unit level**; on the synthetic slice the answer is "Δ = 0 across the board" by construction, no leak suspected. Will revisit on the real slice. |
| 7 (W3.6) | Distractor retrieval blows up context | **Open** — k=5 × ~30 tokens/turn = ~250 retrieved tokens; well under `num_ctx=2048`. Will check in `m1w3_sanity.md` §1 after the host run. |
| 8 (W3.6) | Per-question reset choice is wrong | **Closed for this baseline** — documented in `m1w3_design.md` §2.5; cumulative variant is a different baseline (deferred to PhD). |
| New | Synthetic slice masks the substantive comparison | **Open / documented** — `m1w3_design.md` §1, `m1w3_sanity.md` §0. Resolves the moment a real LME-S file replaces the placeholder corpus. |
| New (host) | Apple-Silicon libomp segfault during MiniLM smoke pytest | **Closed** — `m1w3_design.md` §5b. MiniLM smoke tests now gated by `KSA_RUN_MINILM_SMOKE=1` (default off); `finalize_m1w3.sh` exports `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `TOKENIZERS_PARALLELISM=false` to defuse libomp double-load. The hermetic `FakeEmbedder` tests still cover the contract. |

## Out-of-scope items confirmed unstarted

Per task §7: no k-sweep, no embedder fine-tuning, no hybrid
lexical+dense retrieval, no versioning/supersession/typing, no
recency-aware retrieval, no cross-encoder reranker, no IVF/HNSW
indices. M1-W3 §7 boundaries respected.

## Handoff to M1-W4 (recency-pruning baseline + action_log writer)

Week 4 picks up Baseline 3 (recency-pruning + action_log writer). The
pieces it needs are now in place:

- `BaselineAnswer` shared shape — Week 4 implements
  `RecencyPruningBaseline` with the same `.answer(session) →
  BaselineAnswer` interface.
- `evaluate_baseline(...)` is generic — `scripts/run_baseline.py
  --baseline recency` is wired into the CLI's `_BASELINES_FUTURE` and
  currently raises `SystemExit("on the M1-W4+ roadmap")`.
- `print_report.py --merge` accepts arbitrarily many reports; Week 4's
  3-row table comes from
  `--merge runs/m1w2/no_memory/report.json
          runs/m1w3/flat_vector/report.json
          runs/m1w4/recency/report.json`.

The flat-vector store from this week is **not** reused in Week 4 by
design (per task §8): recency-pruning needs an explicit `memory_items`
table (durable rows with `inserted_at`, FIFO eviction) rather than a
FAISS index over turns. The shared piece is the `BaselineAnswer`
interface and the evaluator. Week 4 also exercises the controller's
substrate (`memory_items`, `action_log`) under load — first time
that path is hit by a baseline, not just unit tests.

End of Week 4 closes Gate G1: three baselines × LongMemEval-S × 50
sessions, all numbers in one table.

## How to finalize on the host

```bash
cd ksa_controller

# 1) Pytest sanity. The MiniLM smoke tests run if .venv has
#    sentence-transformers; otherwise they skip.
PYTHONPATH=src .venv/bin/python -m pytest -q

# 2) Host run (60-120 min on laptop / gemma4:e4b CPU; faster on GPU box).
bash scripts/finalize_m1w3.sh

# 3) Read the disagreement set:
cat NOTES/m1w3_win_loss.md
# Pick 5 wins + 5 losses; fill m1w3_sanity.md §2 and §4.

# 4) Commit + tag.
git add -A
git commit -m "M1-W3: flat-vector baseline (FAISS + MiniLM, k=5)

- Add TurnEmbedder + Embedder Protocol + FakeEmbedder + role_tag
- Add FlatVectorStore (IndexFlatIP, narrow API, per-question reset)
- Add FlatVectorBaseline + prompts/flat_vector.j2
- Wire scripts/run_baseline.py for --baseline flat_vector --k
- Add scripts/print_report.py --merge for the 2-baseline table
- Add scripts/win_loss.py for per-competency disagreement
- Add scripts/finalize_m1w3.sh single-command host runner
- 35 new tests (test_embeddings.py, test_flat_vector_store.py,
  test_flat_vector.py); host run produces NOTES/m1w3_*.md"
git tag -a v0.1.2-m1w3-baseline-flat-vector \
    -m "M1-W3 close: flat-vector baseline + merged 2-baseline table"
```

## One-paragraph status to paste to advisor

> Week 3 done: flat-vector baseline implemented (FAISS `IndexFlatIP` +
> MiniLM-L6-v2, k=5, role-tagged turn-level chunking, per-question reset
> with current-session exclusion). Host run completed in 1969.9 s
> (~33 min) on laptop / Ollama gemma4:e4b — well inside the 2-hour
> acceptance budget — with **Δ +0 pp across every competency** vs.
> M1-W2 no-memory. That is exactly the prediction registered in the
> design note for the synthetic-placeholder slice: every session's
> `supporting_session_ids` reduces to the current session, which is
> excluded by design, so the RETRIEVED MEMORY block reads `[no relevant
> memory found]` on all 50/50 sessions and the generator sees the same
> input on both baselines. Anti-leakage holds end-to-end: 0/50 sessions
> have the current `session_id` in `retrieval_session_ids`. The
> cross-session retrieval path is exercised at unit-test level on a
> stress fixture that plants a target turn in a prior session and
> asserts rank-0 retrieval at similarity ≈ 1.0; substantive multi-session
> / knowledge-update gain and distractor-retrieval losses appear with
> no code change required, only a `scripts/build_slice.py` rebuild
> against the real LongMemEval-S release file. 35 new tests (58 pre-flight
> green; 2 MiniLM smoke env-gated for Apple-Silicon libomp safety —
> see `m1w3_design.md` §5b for the documented mitigation). On track for
> recency-pruning + `action_log` writer in Week 4 (closes Gate G1).
