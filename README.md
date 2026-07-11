# KSA Memory Governance

A Git-ready research repository for interpretable, abstention-aware memory governance in long-lived LLM agents. KSA makes explicit **KEEP**, **SUPERSEDE**, and **ABSTAIN** decisions over typed memories with provenance and supersession lineage.

## What is included

- Full KSA controller implementation under `src/ksa/`.
- No-memory, vector, recency, and naive-overwrite baselines.
- Extraction, relation classification, memory operations, orchestration, and evaluation code.
- The frozen 180-item MGP-6 v2 diagnostic package under `benchmarks/mgp6/`.
- Independent annotation artifacts, separated into human and model/mixed evidence.
- A verified offline suite with **420 passing tests and 14 documented skips**, plus scorer-regression tests.
- Colab/GPU/API run scripts and resumable experiment tooling.
- OpenRouter model configuration for Qwen 3.5 9B with Gemma 4 31B judge/fallback.
- Research, thesis, bibliography, figures, and persistent evidence/experiment registries.
- CI, packaging, security, data-license, and release documentation.

Large historical outputs, local Qdrant/MemOS stores, caches, backups, and third-party LongMemEval data are intentionally excluded from Git.

## Repository map

```text
.
├── src/ksa/                 # controller, memory, extraction, inference, baselines, evaluation
├── tests/                   # unit, regression, integration, CLI tests
├── benchmarks/mgp6/         # MGP-6 v2 data, schema, scorer, adapters, annotations
├── benchmarks/longmemeval/  # external-data integration contract
├── configs/                 # active controller, experiments, OpenRouter model config
├── prompts/                 # extraction and relation prompts
├── schema/                  # LinkML, SQL, and JSON schema
├── scripts/                 # experiment, scoring, replay, and validation CLIs
├── deploy/                  # Colab, Ollama, HF, vLLM, and GPU runners
├── data/                    # small compatibility fixtures only
├── docs/                    # architecture, reproducibility, limitations, history, figures
├── research/                # master prompt, literature review, citation audit
├── paper/                   # venue-neutral paper workspace
├── thesis/                  # thesis source and bibliography
├── artifacts/manifests/     # checksums and external-run manifests
└── .github/workflows/ci.yml
```

## Local setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
make setup
make repo-check
make test
make validate-data
make build
```

Heavy model dependencies are optional:

```bash
pip install -e '.[ml]'
```

## OpenRouter configuration

The repository never embeds credentials. Rotate any key that has previously appeared in chat or logs, then set it only in your shell/secret manager:

```bash
export OPENROUTER_API_KEY='...'
cat configs/models/openrouter_qwen_gemma.yaml
```

Configured models:

- Main: `qwen/qwen3.5-9b`
- Preferred judge: `google/gemma-4-31b-it:free`
- Judge fallback: `google/gemma-4-31b-it`

## Scientific status

MGP-6 v2 is a six-category diagnostic slice, not a comprehensive established benchmark. Historical results and fresh confirmation runs must remain distinct. Submission-ready claims require a frozen confirmation split, complete hosted-model runs, and machine-generated tables. See `PROJECT_STATE.md`, `BLOCKERS.md`, and `research/MASTER_EXECUTION_PROMPT.md`.

## Before pushing

Replace `OWNER` in `pyproject.toml` and `CITATION.cff`, confirm the data license, rotate the exposed API key, and run:

```bash
make repo-check
make test
make lint
make typecheck
make build
```
