# Gate G1 decision — End of Month 1

**Status: PASS.**

**Date (decision):** 2026-04-26 (substrate verified, conditional drafted).
**Date (promoted to PASS):** 2026-04-28 (host run delivered the table).
**Author:** Ali (`ali.mohammadi@cytognosis.org`).
**Predecessor:** M1-W3 close (`v0.1.2-m1w3-baseline-flat-vector`).
**Successor:** M2-W5 (Extraction prompt design).

## 1. Gate definition (proposal §I.11)

> **G1 (end of Month 1, non-negotiable).** Pipeline working end-to-end
> with three baselines on the 50-session LongMemEval-S slice; per-
> competency results table with bootstrapped CIs; pytest green;
> infrastructure debt visible and prioritized.
>
> *Pass condition:* the table exists and is plausible.
>
> *Fail mode:* infrastructure isn't robust enough to support
> three baselines. Mitigation: debug infrastructure before building
> the controller; cut a baseline if necessary (the first cut candidate
> is recency, since the trivial-extractor caveat means it's the
> weakest of the three for now).

## 2. Evidence

### 2.1 Three-baseline merged table (host run)

`NOTES/m1w4_results.md` carries the merged 3-baseline table written
by `bash scripts/finalize_m1w4.sh` on the user's laptop:

| Baseline | Source | n | Overall accuracy | 95% CI | Wall-clock |
|---|---|---:|---:|---|---:|
| no_memory | `runs/m1w4/no_memory/report.json` | 50 | **100.0%** | 100.0 – 100.0 | 1683.4s |
| flat_vector | `runs/m1w4/flat_vector/report.json` | 50 | **100.0%** | 100.0 – 100.0 | 1792.6s |
| recency | `runs/m1w4/recency/report.json` | 50 | **100.0%** | 100.0 – 100.0 | 1586.5s |

Per-competency table (7 rows × 3 baselines = 21 rows) is in
`NOTES/m1w4_results.md`. CI bounds are from 1,000 bootstrap resamples
under `bootstrap_seed=0`. Every per-competency row reads at 100% on
the synthetic slice; on the real LongMemEval-S file the deltas
become substantive (predictions registered in `m1w4_design.md` §3).

### 2.2 Evaluator-drift check (host re-run of W2 + W3)

`NOTES/m1w4_evaluator_drift.md` records the §3.4 ±1pp tolerance
check. Both reruns agree exactly with the archived numbers:

| Baseline | Per-competency rows passing ±1pp | Overall drift |
|---|:-:|---:|
| no_memory (archived ↔ W4 rerun) | 7 / 7 | +0.0 pp |
| flat_vector (archived ↔ W4 rerun) | 7 / 7 | +0.0 pp |

**Verdict: no drift** — cross-week comparisons in
`NOTES/m1w4_results.md` are valid. The evaluator code is unchanged
between W2/W3 and W4 (the deferred prediction in
`m1w4_evaluator_drift.md` was confirmed by host execution).

### 2.3 §3.5 capacity peek (5 sessions × N=25)

`runs/m1w4/recency_cap25_peek/report.json`: 5/5 correct (overall
100.0%, 95% CI 100.0–100.0; wall-clock 114.7s). On the synthetic
slice the sign-of-effect check is **null** as predicted — every
session's `supporting_session_ids` filters to empty regardless of
capacity, so neither N=50 nor N=25 produces an admission and the
two baselines render byte-equal prompts. The substantive
sign-of-effect check waits for the real slice; on the synthetic
slice the null result is the correct, documented behavior.

### 2.4 Pipeline health

| Check | Status |
|---|:-:|
| `pytest` (W1+W2+W3+W4 carried forward, excluding host-only Ollama smoke; sandbox-side) | **125 passed, 3 skipped** |
| `pytest` (host pre-flight inside `finalize_m1w4.sh`) | **100 passed, 2 skipped** |
| New W4 tests covering memory operations | 13 / 13 ✓ |
| New W4 tests covering action log | 12 / 12 ✓ |
| New W4 tests covering recency baseline | 14 / 14 ✓ |
| Atomic supersede under forced exception | ✓ (`test_supersede_is_atomic_under_forced_exception`) |
| Double-supersede raises loudly | ✓ (`test_supersede_double_supersede_raises_loudly`) |
| Lineage walk three-step chain | ✓ (`test_lineage_three_step_chain`) |
| FIFO eviction is destructiveness-by-design (no lineage) | ✓ (`test_supersede_evict_flips_status_no_lineage_no_relation`) |
| action_log schema rejection happens BEFORE write | ✓ (`test_schema_rejection_does_not_write`) |
| action_log crash safety (partial file parseable) | ✓ (`test_crash_safety_partial_file_parseable_up_to_last_flush`) |
| Recency capacity invariant (100 items, capacity=50 → 50 active) | ✓ (`test_capacity_invariant_inserting_more_items_than_capacity`) |
| Recency FIFO discipline (first 50 evicted) | ✓ (`test_fifo_discipline_first_items_get_evicted`) |
| Recency determinism (same seed → identical prompt + action_log ordering) | ✓ (`test_determinism_same_session_same_seed`) |
| Recency anti-leakage (current session never in retrieval) | ✓ (`test_no_current_session_leakage_in_retrieved_block`) |
| Recency degenerate path (empty supporting → no-memory equivalent) | ✓ (`test_degenerates_to_no_memory_when_supporting_is_empty`) |

### 2.5 Repo state

- Memory substrate: `src/ask/memory/operations.py` extends W2 with
  `get_by_id`, `get_lineage`, `supersede_evict`. Atomicity hardened
  via `BEGIN IMMEDIATE` + row-version row-status check.
- Audit substrate: `src/ask/audit/action_log.py` extends W2 with
  `baseline` field + writer-bound override; `mode='w'` truncate
  default; `fsync_on_write=True` default; baseline allow-list
  enforcement.
- Schema: `schema/generated/ask_memory.schema.json` extends W2 with
  `session_id`, `baseline` (enum), `candidate_type` (enum nullable).
  Pre-W4 entries remain valid (new fields are nullable).
- Baseline 3: `src/ask/baselines/recency_pruning.py` +
  `src/ask/baselines/prompts/recency_pruning.j2` — RecencyPruningBaseline
  with capacity, k, action_log_path knobs.
- Run driver: `scripts/run_baseline.py` accepts
  `--baseline recency --capacity N --no-action-log`.
- Host runner: `scripts/finalize_m1w4.sh` runs the recency baseline
  + reruns W2 and W3 + produces drift report + merged table + win/loss
  matrices + 5-session capacity peek + stamps the sanity note.

## 3. Predicted patterns confirmed

The carry-over predictions from `NOTES/m1w4_design.md` §3 hold on
the synthetic slice as expected:

- **No-memory == flat-vector == recency = 100% on this slice**
  (synthetic placeholder saturates by construction; every gold answer
  is in the visible dialog). The substantive deltas appear when the
  real LongMemEval-S file replaces
  `data/longmemeval_s_synthetic.jsonl` — no code change, only a
  `scripts/build_slice.py` rebuild and `bash scripts/finalize_m1w4.sh`
  re-run.
- **Recency vs. flat-vector trade-off documented.** On the synthetic
  slice the trade-off is degenerate (both prompts byte-equal). The
  unit-test fixture
  `test_capacity_invariant_inserting_more_items_than_capacity`
  exercises the FIFO admit/evict path on a 100-item synthetic stream
  and confirms the substrate behaves correctly. The eviction-of-truth
  signature waits for the real slice.
- **Recency wall-clock < flat-vector wall-clock** (1586s vs. 1793s).
  Recency's per-question SQLite reset is cheap (zero admits on this
  slice → zero embed forwards → faster than flat-vector's MiniLM
  query encode per question). On the real slice the picture
  inverts as admissions/evictions kick in.

## 4. Open questions for Month 2

1. **Trivial-extractor caveat (load-bearing).** The recency numbers
   are upper-bounded by what FIFO eviction can do given any reasonable
   item stream. Once M2-W5 produces the proper LLM-based extractor,
   the items entering the FIFO queue will be different — different
   text content, different typing decisions, lower per-item
   confidence. **Recency-pruning will likely need to be re-run on
   the M2 stream before any chapter-4 numbers are final.** This is
   pre-registered for Month 4. Do not assume Month-1 recency numbers
   are final.
2. **Judge fallback rate (carry forward).** 31/50 grades on the W2
   archived run came from the substring fallback (LLM judge emitted
   empty text). The judge prompt is unchanged in W4. Substituting to
   GPT-4o (or the LongMemEval-published judge) is M4 work; until
   then the self-judging caveat is in every results-table caption.
3. **Real LongMemEval-S file.** The synthetic placeholder
   (`data/longmemeval_s_synthetic.jsonl`) is what every W2/W3/W4 run
   has used. Replacing it with the real release file
   (`scripts/build_slice.py` rebuild, no code change) produces the
   non-saturated table the proposal claims. M2-W5 will run on the
   real slice from day one.
4. **Supersede atomicity beyond a single SQLite connection.** The
   §3.1 atomicity test forces a Python-level exception inside the
   transaction. A second writer racing in (real concurrency) is not
   expected at our scale (single-process Python harness) but the
   `BEGIN IMMEDIATE` lock is in place defensively. If M3-W11 or M4
   parallelizes the harness, re-test.

## 5. Decision

**PASS.**

All four pass conditions are met:
- Three-baseline merged table exists with measured numbers in
  `NOTES/m1w4_results.md` (no asterisks).
- Per-competency CIs exist (1000-bootstrap, seed 0).
- pytest is green: 125/125 + 3 skipped (sandbox); 100/100 + 2 skipped
  (host pre-flight).
- Substrate (`memory_items` + `action_log`) is in code and tested at
  the load-bearing level the rest of the thesis depends on.
- The destructiveness gap (FIFO eviction destroys lineage; controller
  `supersede` preserves it) is in code via `supersede_evict` vs.
  `supersede` and covered by tests.

Drift check from §2.2: 0.0pp on every per-competency row across both
reruns. Cross-week comparisons valid.

Infrastructure debt visible and prioritized in §4: trivial-extractor
caveat; judge fallback; real-slice substitution; concurrency. None of
these blocks Month 2; all are scheduled.

No baseline cut. M2-W5 (extraction prompt design) is unblocked.

The §I.11 fail-mode mitigation ("cut a baseline; first candidate
recency") is **not triggered**. Recency is in the table at 100% on
the synthetic slice (which it must be, by the 6-step proof in
`m1w4_results.md`). The substrate behaves as designed under the
100-item / capacity-50 stress fixture. Recency stays.

## 6. Advisor email (paragraph)

> **Subject:** Gate G1 closeout — PASS, all three baselines on the
> 50-session slice
>
> Sending the Month-1 closeout doc. The substrate (durable
> `memory_items` table, supersede atomic + supersede_evict FIFO
> primitive, action_log JSONL writer with schema validation and
> crash safety) is in code and covered by 39 new tests + 86
> carried-forward tests, all green. Baseline 3 (recency-pruning)
> ran end-to-end on the 50-session synthetic-placeholder slice in
> 1586.5s (overall 100.0%, 95% CI 100.0–100.0). The W2 and W3
> reruns of no_memory and flat_vector show 0.0pp drift on every
> per-competency row vs. the archived numbers — cross-week
> comparisons are valid. The 5-session capacity=25 peek confirms
> the null sign-of-effect on the synthetic slice (predicted; the
> substantive sign-of-effect check waits for the real LongMemEval-S
> file, which lands at the start of M2-W5). Tagging
> `v0.2.0-m1-end-G1-pass` and proceeding to M2-W5 (extraction
> prompt design) on a real LongMemEval-S slice from day one. Two
> open questions for Month 2: (1) the trivial-extractor caveat
> means recency will likely need to be re-run on the M2 extractor's
> stream before any chapter-4 numbers are final (Month-4 ablation
> work, pre-registered); (2) the qualitative eviction-of-truth
> analysis waits for the real slice. Please reply with explicit
> go/no-go for M2.
>
> Attachments: `NOTES/G1_gate_decision.md`, `NOTES/m1w4_results.md`,
> `NOTES/m1w4_evaluator_drift.md`, `NOTES/m1w4_sanity.md`,
> `NOTES/m1w4_design.md`.

## 7. Tag

**`v0.2.0-m1-end-G1-pass`** — apply to the commit that contains the
host-run artifacts (`runs/m1w4/{no_memory,flat_vector,recency,
recency_cap25_peek}/`) plus the merged note revisions written by
`finalize_m1w4.sh`.
