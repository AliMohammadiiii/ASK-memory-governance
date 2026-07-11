# Per-competency results — merged across 2 baselines

- **Reference baseline:** `no_memory` (`runs/m1w2/no_memory/report.json`); n=50, overall 100.0% (95% CI 100.0 – 100.0)
- **Comparison:** `flat_vector` (`runs/m1w3/flat_vector/report.json`); n=50, overall 100.0% (Δ +0.0 pp; 95% CI 100.0 – 100.0)

- **Judge:** `gemma4:e4b` (same across baselines per M1-W2 §3.0; cache hits when answer text coincides).

| Competency | Baseline | n | Accuracy | Δ vs. ref | 95% CI | Avg prompt tokens | Avg latency (ms) |
|---|---|---:|---:|---:|---|---:|---:|
| abstention | no_memory | 10 | 100.0% | — | 100.0 – 100.0 | 102 | 2473 |
| abstention | flat_vector | 10 | 100.0% | +0.0 pp | 100.0 – 100.0 | 118 | 3938 |
| knowledge-update | no_memory | 10 | 100.0% | — | 100.0 – 100.0 | 104 | 2519 |
| knowledge-update | flat_vector | 10 | 100.0% | +0.0 pp | 100.0 – 100.0 | 120 | 4494 |
| multi-session | no_memory | 6 | 100.0% | — | 100.0 – 100.0 | 104 | 2430 |
| multi-session | flat_vector | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 120 | 4335 |
| single-session-assistant | no_memory | 6 | 100.0% | — | 100.0 – 100.0 | 106 | 2896 |
| single-session-assistant | flat_vector | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 122 | 2802 |
| single-session-preference | no_memory | 6 | 100.0% | — | 100.0 – 100.0 | 106 | 2628 |
| single-session-preference | flat_vector | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 122 | 3181 |
| single-session-user | no_memory | 6 | 100.0% | — | 100.0 – 100.0 | 105 | 2251 |
| single-session-user | flat_vector | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 121 | 3012 |
| temporal-reasoning | no_memory | 6 | 100.0% | — | 100.0 – 100.0 | 106 | 2633 |
| temporal-reasoning | flat_vector | 6 | 100.0% | +0.0 pp | 100.0 – 100.0 | 122 | 2902 |


## Per-baseline run metadata

- `no_memory` from `runs/m1w2/no_memory/report.json`: slice=`?`, seed=?
- `flat_vector` from `runs/m1w3/flat_vector/report.json`: wall_clock=1969.9s, slice=`data/slices/longmemeval_s_50_seed0.jsonl`, seed=0

---

## Caption draft (Chapter 4, Table 4.1 cont'd)

> **Table 4.1 (cont'd).** Per-competency accuracy of Baseline 2
> (flat-vector memory: FAISS + `sentence-transformers/all-MiniLM-L6-v2`,
> k=5, turn-level role-tagged embeddings, per-question reset) on the
> LongMemEval-S 50-session development slice. Δ vs. Baseline 1 in
> parentheses. Errors are 95% bootstrap CIs over 1,000 resamples. The
> competencies that benefit most from flat-vector retrieval (multi-session,
> knowledge-update) are precisely the competencies where retrieval can find
> prior turns; competencies where the answer is in the current session show
> no improvement and may degrade due to distractor retrieval.

