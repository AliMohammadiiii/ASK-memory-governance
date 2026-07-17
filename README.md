# KSA Memory Governance

A Git-ready research repository for interpretable, abstention-aware memory governance in long-lived LLM agents. KSA makes explicit **KEEP**, **SUPERSEDE**, and **ABSTAIN** decisions over typed memories with provenance and supersession lineage.

## What is included

- Full KSA controller implementation under `src/ksa/`.
- No-memory, vector, recency, and naive-overwrite baselines.
- Extraction, relation classification, memory operations, orchestration, and evaluation code.
- The frozen 180-item MGP-6 v2 diagnostic package under `benchmarks/mgp6/`.
- Annotation audit artifacts separated into independent-human and model-panel evidence;
  raw human labels are withheld from the public bundle pending redistribution consent.
- A verified offline test suite plus scorer-regression tests (see the dated validation report for exact counts).
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

The repository never embeds credentials. Use a newly authorized key and set it
only in your shell or secret manager. A prior authorization attempt stopped
before inference and is not a reusable experiment credential:

```bash
export OPENROUTER_API_KEY='...'
cat configs/models/openrouter_qwen_gemma.yaml
```

Configured models:

- Main: `qwen/qwen3.5-9b`
- Preferred judge: `google/gemma-4-31b-it:free`
- Judge fallback: `google/gemma-4-31b-it`

## Scientific status

MGP-6 v2 is a six-category, author-designed pilot diagnostic, not an independent
benchmark. Its held-out split is not construct-valid: a conflict-type-only
lookup fitted on train and development obtains 1.000 test accuracy, while the
reference rule policy obtains 0.8889 and the structured LLM policy obtains
0.9000. The released audit therefore treats the policy results as diagnostic,
reports family-clustered uncertainty and asymmetric error costs, and makes no
superiority or population-safety claim. LongMemEval has no eligible final result
and is excluded from the main manuscript. See
`artifacts/analysis/mgp6_validity_audit.md`,
`benchmarks/mgp6/MGP6_V3_INDEPENDENT_PROTOCOL.md`, and
`docs/audit/SCIENTIFIC_SOURCE_OF_TRUTH.md`.

## Before pushing

After creating the public host, add its real repository and issue URLs (no
placeholder URL is shipped). Record human-annotation redistribution consent if
the raw labels will be published, complete the independent v3 confirmation
protocol before making generalization claims, and run:

```bash
make repo-check
make test
make lint
make typecheck
make build
make paper-audit
```
