# Win / loss / tie — `flat_vector` vs. `no_memory`

- **Reference judgments:** `runs/m1w2/no_memory/judgments.jsonl`
- **New judgments:** `runs/m1w3/flat_vector/judgments.jsonl`

Per-competency cell counts. **new-only** = `new` improved over `ref`; **ref-only** = `new` regressed; **both-correct** / **both-wrong** = agreement. The `new-only` and `ref-only` cells are exactly the disagreement set the §3.5 sanity check spot-checks.

| Competency | n | both-correct | new-only (gain) | ref-only (loss) | both-wrong |
|---|---:|---:|---:|---:|---:|
| abstention | 10 | 10 | 0 | 0 | 0 |
| knowledge-update | 10 | 10 | 0 | 0 | 0 |
| multi-session | 6 | 6 | 0 | 0 | 0 |
| single-session-assistant | 6 | 6 | 0 | 0 | 0 |
| single-session-preference | 6 | 6 | 0 | 0 | 0 |
| single-session-user | 6 | 6 | 0 | 0 | 0 |
| temporal-reasoning | 6 | 6 | 0 | 0 | 0 |
| **all** | 50 | 50 | 0 | 0 | 0 |

Net = (new-only) − (ref-only) = 0 sessions across all competencies.

## Disagreement session ids (read these in `judgments.jsonl`)

