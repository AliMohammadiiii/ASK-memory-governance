# MGP-6 v4.3 integration: repository discovery

**Status:** public integration and the private-data boundary were committed as
`41f7ceeb38c971874b52578c4b622a704b992715`; follow-on development work is on
`mgp6-v43-experiments`.

## Repository identity

- Root: `/Users/ali/Documents/20_Academics/Master/Master/ksa-memory-governance`
- Discovery branch: `preserve-pre-mgp6-v43-integration`
- Integration base commit: `41f7ceeb38c971874b52578c4b622a704b992715`
- Follow-on branch: `mgp6-v43-experiments`
- Preservation commits: `a4fe760`, `ca0febc`
- Python: `3.14.6`
- Serena project: `ask-memory-governance` (activated before discovery)

## Preservation and current authority

The initial discovery found conflicting changes in target files. The user then
preserved them in the commits above and declared the ASK migration authoritative:

- `src/ask/`
- `schema/ask_memory.yaml`
- `schema/generated/ask_memory.schema.json`
- `thesis/MASTERS_THESIS_ASK_MGP6.md`
- `paper/paper_1/`

The old KSA package was not restored or recreated. Historical v3.3.1 paths were
classified and left untouched. The integration changes are recorded in
`INTEGRATION_CHANGELOG.md`.

Immediately after the integration base commit, there were no tracked-file
changes. The working tree retained only the explicitly classified historical
untracked paths (v3.3.1 archives, prior analysis reports, deliverables, and
LongMemEval reporting material); they were not staged or modified.

## Existing repository conventions

| Area | Existing location/convention |
| --- | --- |
| MGP-6 benchmark | `benchmarks/mgp6/`; v2 data and harness are colocated here, with `data/`, `systems/`, `run_5systems.py`, `run_llm_controller.py`, `metrics_mgp6.py`, and `validate_mgp6.py`. |
| Earlier MGP-6 material | `benchmarks/mgp6/v3_human_pack/`; `releases/MGP6_v3.3.1/`; historical v1 data under `data/`. |
| Core evaluator | `src/ask/eval/mgp6.py` and `src/ask/eval/mgp6_schema.py`. |
| Current runner | `scripts/run_mgp6.py`; the v2 harness also has self-contained runner scripts in `benchmarks/mgp6/`. |
| Baselines/controller | `src/ask/baselines/`, `src/ask/controller/`, and MGP-6 system IDs `b1`, `b2`, `b3`, `b4`, and `controller`. |
| Configuration | `configs/`, including `configs/eval_mgp6_final.yaml` and `configs/controller_active.yaml`. |
| Run and result artifacts | `runs/`, `runs_local/`, `artifacts/results/`, and reports in `reports/`. |
| External benchmark | `benchmarks/longmemeval/`, `src/ask/data/longmemeval.py`, `src/ask/eval/longmemeval.py`, and scripts under `scripts/evaluation/`. Its documentation describes it as a separate external integration. |
| Paper | LaTeX project at `paper/paper_1/main.tex`, with benchmark and evaluation sections at `sections/04_mgp6.tex`, `06_experimental_setup.tex`, `07_results.tex`, and limitations at `09_discussion_limitations.tex`. |
| Thesis | Markdown thesis material under `thesis/`; the authoritative source is currently ambiguous because its tracked KSA file is deleted while an ASK-named file is untracked. |
| Tests | Pytest, flat `tests/` layout; existing MGP-6 coverage includes `test_mgp6_schema.py`, `test_mgp6_eval.py`, and `test_mgp6_v2_scorer_regression.py`. |
| CI | `.github/workflows/ci.yml` runs repository validation, pytest (excluding network), Ruff, mypy, and a package build. |
| Ignore rules | `.gitignore` already ignores `runs/`, `runs_local/`, external data, and generated publication output, but it has no narrow MGP-6 v4.3 private-data rule. It is itself modified, so it was not changed. |

## Implemented path mapping

See `PATH_MAPPING.json`. The selected paths reuse the existing benchmark,
source, configuration, run, and release roots: public v4.3 material is now
integrated beneath `benchmarks/mgp6/mgp6_v4_3/`, the public release mirror is
under `releases/MGP6_v4.3.0/`, and private material is only beneath the ignored
`.private/benchmarks/mgp6/v4.3/` boundary. Historical versions remain intact.

## Generated-artifact policy

The existing tracked LaTeX build outputs (`main.aux`, `main.fdb_latexmk`,
`main.fls`, `main.bbl`, `main.blg`, `main.out`, and
`AliMohammadi-draft.pdf`) are preserved unchanged. The tracked historical
`08_downstream_analysis.tex.bak_v11` is explicitly allowlisted in repository
validation; no generated artifact was deleted merely because it is generated.
