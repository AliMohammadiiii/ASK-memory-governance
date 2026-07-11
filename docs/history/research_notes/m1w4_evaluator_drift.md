# M1-W4 evaluator-drift report

Tolerance: ±1.0 pp on per-competency accuracy.

§3.4 acceptance: re-runs of W2 and W3 baselines drift from the archived numbers by less than ±1pp. Larger drift means the evaluator was modified between weeks and earlier numbers are no longer comparable. Document the offending row(s) below; the Gate G1 decision must reflect this.

### `no_memory`: archived `runs/m1w2/no_memory/report.json` ↔ current `runs/m1w4/no_memory/report.json`

| Competency | Archived acc | Current acc | Δ (pp) | Within ±1pp? |
|---|---:|---:|---:|:-:|
| abstention | 100.0% | 100.0% | +0.0 | ✓ |
| knowledge-update | 100.0% | 100.0% | +0.0 | ✓ |
| multi-session | 100.0% | 100.0% | +0.0 | ✓ |
| single-session-assistant | 100.0% | 100.0% | +0.0 | ✓ |
| single-session-preference | 100.0% | 100.0% | +0.0 | ✓ |
| single-session-user | 100.0% | 100.0% | +0.0 | ✓ |
| temporal-reasoning | 100.0% | 100.0% | +0.0 | ✓ |
| **overall** | **100.0%** | **100.0%** | **+0.0** | **✓** |

### `flat_vector`: archived `runs/m1w3/flat_vector/report.json` ↔ current `runs/m1w4/flat_vector/report.json`

| Competency | Archived acc | Current acc | Δ (pp) | Within ±1pp? |
|---|---:|---:|---:|:-:|
| abstention | 100.0% | 100.0% | +0.0 | ✓ |
| knowledge-update | 100.0% | 100.0% | +0.0 | ✓ |
| multi-session | 100.0% | 100.0% | +0.0 | ✓ |
| single-session-assistant | 100.0% | 100.0% | +0.0 | ✓ |
| single-session-preference | 100.0% | 100.0% | +0.0 | ✓ |
| single-session-user | 100.0% | 100.0% | +0.0 | ✓ |
| temporal-reasoning | 100.0% | 100.0% | +0.0 | ✓ |
| **overall** | **100.0%** | **100.0%** | **+0.0** | **✓** |

---

**Verdict: no drift** — all per-competency accuracies match their archived counterparts within ±1pp. Cross-week comparisons in NOTES/m1w4_results.md are valid.
