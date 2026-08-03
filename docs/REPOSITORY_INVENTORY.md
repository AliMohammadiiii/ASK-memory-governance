# Repository inventory

Audit date: 2026-08-02

## Authoritative locations

| Logical location | Repository-relative or configured path | Authority | Mutation policy |
|---|---|---|---|
| ASK source repository | `.` | canonical source, tests, public benchmark material, tracked evidence, paper source | editable through reviewed changes |
| MGP-6 v4.3 private evaluation material | `.private/benchmarks/mgp6/v4.3/` | private labels, mappings, annotations, and hidden scoring contract | do not expose to model-facing code or public release |
| MGP-6 v4.3 consumed hidden run | `runs/mgp6_v43/final_hidden/` | frozen local run evidence | historical and consumed; no tuning or new comparisons |
| LongMemEval V12 run | `runs_local/lme_final_controller_v12_qwen_180/` | frozen local downstream evidence | historical; preserve original manifests and anomalies |
| Historical MGP-6 archive | `../mgp6_v2/` | read-only historical evidence | do not consolidate by copying |
| Historical controller archive | `../ksa_controller/` when present | read-only historical evidence | do not consolidate by copying |
| Current manuscript release | `$ASK_PAPER_PACKAGE` | generated delivery package; observed locally under the user's Downloads directory | regenerate from canonical paper source, do not edit archives in place |

`$ASK_PAPER_PACKAGE` should point to `MGP6_Paper_TMLR_Submission` when release
comparison is required. No machine-specific absolute path is stored here.

## Tracked project structure

| Path | Contents | Boundary |
|---|---|---|
| `src/ask/` | maintained Python implementation | public source |
| `src/ask/protocol/` | executable ASK reference contract and adapters | public source |
| `tests/` | unit, conformance, regression, and release tests | public source |
| `benchmarks/mgp6/` | public v2 material, public v4.3 train/development material, validators, and restricted annotation summaries | mixed; governed by release allowlist |
| `schema/` | persisted and protocol serialization schemas | public source |
| `configs/`, `prompts/` | controller, provider, experiment, and prompt configuration | public after secret and path scan |
| `scripts/` | evaluation, analysis, release, and validation commands | public source |
| `artifacts/` | tracked aggregate evidence and manifests | public only when source terms allow |
| `paper/` | canonical manuscript source and generated LaTeX fragments | public or anonymous supplement after scan |
| `reports/` | derived audits and scientific summaries | public after claim and anonymity checks |
| `runs/`, `runs_local/`, `data/`, `.private/` | ignored local run and data material | private or restricted; never CI input |

## Current repository state

- Git root and Serena project root match.
- Starting branch: `mgp6-v43-experiments`.
- Starting commit: `51decd61c297cdd2af0f3227e79307baa4df5697`.
- The worktree was clean before this implementation session.
- The repository contains about 790 tracked files. Local data and run outputs
  account for most of the approximately 17 GB working-directory footprint.
- No root `AGENTS.md` existed at discovery time; repository-specific instructions
  were added without modifying the parent workspace instructions.

## Source precedence

1. Raw predictions, judgments, action logs, and gold contracts.
2. Deterministic analyses regenerated from those artifacts.
3. Versioned manifests and derived provenance notes.
4. Claim ledger and generated paper fragments.
5. Narrative reports and manuscript prose.

Historical manifests are evidence even when incorrect. They are never rewritten
to make a run appear cleaner than it was.
