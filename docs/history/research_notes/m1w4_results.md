# Per-competency results — merged across 3 baselines

- **Reference baseline:** `no_memory` (`runs/m1w4/no_memory/report.json`); n=50, overall 100.0% (95% CI 100.0 – 100.0)
- **Comparison:** `flat_vector` (`runs/m1w4/flat_vector/report.json`); n=50, overall 100.0% (Δ +0.0 pp; 95% CI 100.0 – 100.0)
- **Comparison:** `recency` (`runs/m1w4/recency/report.json`); n=50, overall 100.0% (Δ +0.0 pp; 95% CI 100.0 – 100.0)

- **Judge:** `gemma4:e4b` (same across baselines per M1-W2 §3.0; cache hits when answer text coincides).

| Competency | Baseline | n | Accuracy | Δ vs. ref | 95% CI | Avg prompt tokens | Avg latency (ms) |
|---|---|---:|---:|---:|---|---:|---:|
| abstention | no_memory | 10 | 100.0% | — | 100.0 – 100.0 | 102 | 3297 |
| abstention | flat_vector | 10 | 100.0% | +0.0 pp | 100.0 – 100.0 | 118 | 3857 |
| abstention | recency | 10 | 100.0% | +0.0 pp | 100.0 – 100.0 | 118 | 2617 |
| knowledge-update | no_memory | 10 | 100.0% | — | 100.0 – 100.0 | 104 | 2919 |
| knowledge-update | flat_vector | 10 | 100.0% | +0.0 pp | 100.0 – 100.0 | 120 | 3939 |
| knowledge-update | recency | 10 | 100.0% | +0.0 pp | 100.0 – 100.0 | 120 | 2918 |
| multi-session | no_memory | 6 | 100.0% | — | 100.0 – 100.0 | 104 | 3481 |
| multi-session | flat_vector | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 120 | 3127 |
| multi-session | recency | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 120 | 2869 |
| single-session-assistant | no_memory | 6 | 100.0% | — | 100.0 – 100.0 | 106 | 2862 |
| single-session-assistant | flat_vector | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 122 | 4099 |
| single-session-assistant | recency | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 122 | 3108 |
| single-session-preference | no_memory | 6 | 100.0% | — | 100.0 – 100.0 | 106 | 3055 |
| single-session-preference | flat_vector | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 122 | 3760 |
| single-session-preference | recency | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 122 | 2790 |
| single-session-user | no_memory | 6 | 100.0% | — | 100.0 – 100.0 | 105 | 2722 |
| single-session-user | flat_vector | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 121 | 4127 |
| single-session-user | recency | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 121 | 2480 |
| temporal-reasoning | no_memory | 6 | 100.0% | — | 100.0 – 100.0 | 106 | 3913 |
| temporal-reasoning | flat_vector | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 122 | 4665 |
| temporal-reasoning | recency | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 122 | 2877 |


## Per-baseline run metadata

- `no_memory` from `runs/m1w4/no_memory/report.json`: wall_clock=1683.4s, slice=`data/slices/longmemeval_s_50_seed0.jsonl`, seed=0
- `flat_vector` from `runs/m1w4/flat_vector/report.json`: wall_clock=1792.6s, slice=`data/slices/longmemeval_s_50_seed0.jsonl`, seed=0
- `recency` from `runs/m1w4/recency/report.json`: wall_clock=1586.5s, slice=`data/slices/longmemeval_s_50_seed0.jsonl`, seed=0

---

## Caption draft (Chapter 4, Table 4.1 cont'd)

> **Table 4.1 (cont'd).** Per-competency accuracy of Baseline 3
> (recency-pruning: FIFO eviction at capacity N=50 over per-user-turn
> memory items, identical retrieval to Baseline 2) on the LongMemEval-S
> 50-session development slice. Δ vs. Baselines 1 and 2 in parentheses.
> Errors are 95% bootstrap CIs over 1,000 resamples. Recency-pruning
> trades retention for noise: gains over no-memory on multi-session
> reasoning, but eviction discards information that flat-vector retains,
> producing a context-dependent gap. The trivial extractor used here is
> replaced by an LLM-based extractor in Chapter 4.X; recency-pruning is
> rerun in §4.X with the updated item stream.

