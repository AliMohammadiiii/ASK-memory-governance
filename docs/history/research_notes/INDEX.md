# NOTES index

One-line summaries of every Month-1 working note. By Month 5 these
become the "where did I write that" lookup — invest the discipline
now.

## Month 1, Week 1 (data + environment)

- `gap_audit_m1w1.md` — pre-flight: what infrastructure existed, what
  was missing, the M1-W1 acceptance gap.
- `longmemeval_mapping.md` — LongMemEval-S → controller mapping
  (which competencies exercise which controller pieces).
- `env.md` — laptop + GPU box environment notes; OS, Python, Ollama
  setup; libomp segfault root-cause + mitigation.
- `inference_bench.md` — Ollama tokens/sec on the host model,
  cold-load times, num_ctx usage profile.
- `eval_protocol.md` — judge prompt, substring fallback, bootstrap CI
  protocol, cache key shape.
- `run_local_smoke.md` — running the smoke E2E test on the laptop.
- `finalize_m1w1.md` — closing W1: tag + handoff to W2.
- `status_m1w1.md` — status snapshot at end of W1.

## Month 1, Week 2 (Baseline 1 — no-memory)

- `m1w2_results.md` — single-baseline per-competency table.
- `m1w2_sanity.md` — sanity-check note: judge fallback proportion,
  predicted-vs-observed gap, anomalies carried forward.
- `status_m1w2.md` — status snapshot at end of W2.

## Month 1, Week 3 (Baseline 2 — flat-vector)

- `m1w3_design.md` — the four design decisions (MiniLM, role tagging,
  k=5, per-question reset) with literature justifications and the
  Apple-Silicon libomp segfault mitigation.
- `m1w3_results.md` — merged 2-baseline table (no_memory ↔
  flat_vector), per-competency Δ.
- `m1w3_win_loss.md` — per-competency disagreement matrix.
- `m1w3_sanity.md` — sanity-check note: 9-field telemetry validation,
  10-example win/loss/distractor breakdown (empty on synthetic slice;
  re-fillable on real slice).
- `m1w3_sanity.template.md` — template the host runner stamps from.
- `status_m1w3.md` — status snapshot at end of W3.

## Month 1, Week 4 (Baseline 3 — recency-pruning + Gate G1 close)

- `m1w4_design.md` — three design decisions (trivial extractor,
  capacity N=50, retrieval same-as-flat-vector) with the
  destructiveness-gap framing for Chapter 4.
- `m1w4_results.md` — merged 3-baseline table (no_memory ↔
  flat_vector ↔ recency); recency line is synthetic-slice prediction
  pending host run, with proof sketch.
- `m1w4_evaluator_drift.md` — ±1pp drift report from the W2/W3 reruns
  (predicted 0.0pp; the evaluator code is unchanged from W3).
- `m1w4_sanity.md` — sanity-check note: 13-field telemetry,
  eviction-of-truth qualitative table (empty on synthetic slice;
  fillable on real slice), capacity peek.
- `m1w4_sanity.template.md` — template the host runner stamps from.
- `m1w4_win_loss.md` — per-competency disagreement matrices (recency
  vs. flat_vector; recency vs. no_memory). Filled by host run.
- `G1_gate_decision.md` — **Gate G1 close.** Status: **PASS**
  (host run completed 2026-04-27; recency 100% in 1586.5s; W2/W3
  reruns drift 0.0pp; capacity peek null on synthetic as predicted).
  Decision rationale + tag scheme.
- `m4w14_pipeline_audit_2026-05-29.md` — **P0 extraction bug audit.** Invalidates
  `runs/m4w14`/`runs/m4w15`; documents the schema/repair fix, the 14→48/60
  recall recovery proof, the new `superseded_recoverability` (H2) metric and
  run-level sanity checks, and the exact re-run procedure.
- `m4w13_50_llama_b1_b2_b3_audit.md` — audited the partial Ollama
  thesis-profile LongMemEval-S 50-item artifacts from `runs(2).zip` and
  `runs(3).zip`; B1 no-memory accepted at 18.0%, B2 flat-vector accepted at
  38.0%, B3 recency accepted at 22.0%, and B4/controller remain to run.
- `INDEX.md` — this file.

## Repo tags (Month 1)

- `v0.1.0-m1w1-data-env` — W1 close (data slicer + env baseline).
- `v0.1.1-m1w2-baseline-no-memory` — W2 close (Baseline 1).
- `v0.1.2-m1w3-baseline-flat-vector` — W3 close (Baseline 2).
- `v0.2.0-m1w4-substrate` — W4 substrate-only (memory_items + action_log
  + recency-pruning code, all tests green, no host run yet).
- `v0.2.0-m1-end-G1-pass` — Gate G1 close. Apply to the commit
  containing `runs/m1w4/{no_memory,flat_vector,recency,recency_cap25_peek}/`
  plus the merged-note revisions written by `finalize_m1w4.sh`.
