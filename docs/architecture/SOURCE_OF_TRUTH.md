# Sources of truth

This page assigns one authority for each repository concern. It complements the
scientific claim rules in `../audit/SCIENTIFIC_SOURCE_OF_TRUTH.md`.

| Concern | Authority | Secondary material |
|---|---|---|
| Installable code | `src/ask/` | thin commands under `scripts/` |
| ASK protocol | `src/ask/protocol/` and `../ASK_PROTOCOL.md` | manuscript explanations |
| Public benchmark contracts | `benchmarks/` | reports and manuscript summaries |
| Private evaluation material | configured `.private/` paths | hashes and public aggregate records |
| Maintained defaults | `configs/` | command examples |
| Experiment records | `experiments/` and run manifests | narrative run notes |
| Prompt identity | `prompts/registry.yaml` and prompt bytes | prompt descriptions in manuscripts |
| Raw predictions and judgments | registered artifact or local evidence paths | derived reports |
| Claim values | `claims/claims.csv`, source hashes, and generating commands | paper and thesis prose |
| Public/private policy | `release/PUBLIC_PRIVATE_MATRIX.csv` | release checklists |
| Paper | `paper/paper_1/main.tex` and its included sources | rendered local PDF |
| Thesis | `thesis/latex/main.tex` and its included sources | Markdown and review exports |
| Current limitations | `../limitations.md` | `../known_limitations.md` compatibility link |
| Current repository instructions | root `README.md`, `Makefile`, and this directory | dated reports |
| Historical decisions | `docs/history/` | references from current documents |

## Evidence precedence

When two sources disagree, use this order:

1. source data, raw predictions, judgments, action logs, and label contracts;
2. deterministic analyses generated from those inputs;
3. provenance manifests and claim checks;
4. maintained protocols and audit documents;
5. paper and thesis prose;
6. presentation material and historical notes.

Later evidence may change the interpretation of an older result. The older
manifest remains an accurate record of what was stored at that time. A derived
manifest records parentage and anomalies instead of editing the parent.

## Generated output

Build directories, caches, compiled documents, release ZIPs, expanded handoff
trees, local databases, run directories, and private data are not source. Their
presence cannot change a claim or package version. A released archive must have
a checksum and per-file manifest, and it must be reproducible from tracked
source plus explicitly registered external inputs.
