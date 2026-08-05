# Generated-file registry

| Output | Source and command | Version control policy |
|---|---|---|
| `build/`, `dist/`, wheel metadata | `make build` | ignored; rebuild for each release |
| Python and tool caches | Python, pytest, Ruff, mypy | ignored; `make clean` removes maintained scopes |
| `paper/**/compiled/` | LaTeX source below `paper/` | ignored; paper source and verified fragments are tracked |
| `thesis/latex/compiled/` | `thesis/latex/main.tex` and included sources | ignored; rebuild for review |
| `advisor_handoff/` | `make advisor-package` | ignored; `make advisor-clean` removes it safely |
| `final_release/` | `scripts/release/build_final_release.py` | ignored; archive and checksum are release outputs |
| `runs/`, `runs_local/` | evaluation commands and registered configuration | ignored; promote approved evidence through manifests |
| Human-pack `dist/` | `build_human_pack_docx.py` | ignored; source Markdown and forms are tracked |
| Paper numeric fragments | generating scripts under `scripts/paper/` | tracked because the manuscripts include them; drift-checked |
| Claim ledger and source inventory | commands under `scripts/claims/` and `scripts/research/` | tracked because they are audit evidence; regenerate and review diffs |
| Derived research manifests | provenance builders under `scripts/provenance/` | tracked when approved; parent hashes are mandatory |

Tracked generated evidence is an exception to the general ignore rule. Its
value is auditability, and each such file must have a deterministic producer or
an explicit provenance statement.
