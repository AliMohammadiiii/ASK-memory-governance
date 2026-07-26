# ASK Memory Governance

ASK is an interpretable memory-revision controller for long-lived LLM agents. It
makes explicit **KEEP**, **SUPERSEDE**, or **ABSTAIN** decisions over typed
memories and preserves provenance and supersession lineage.

This repository is both a Python package and a research artifact. The maintained
runtime lives under `src/ask`; benchmark protocols, frozen evidence, paper and
thesis sources, and historical experiment material are kept in clearly separated
directories.

## Release status

- Package version: `0.2.0`
- Supported Python: 3.11 and 3.12
- Default verification: offline and credential-free
- External model and LongMemEval runs: opt-in; data and credentials are not
  redistributed
- Scientific scope: MGP-6 v2 is an author-designed diagnostic whose held-out
  construct-validity gate failed; no final LongMemEval capability result is
  claimed

The current scientific interpretation is maintained in
`docs/audit/SCIENTIFIC_SOURCE_OF_TRUTH.md`. The documentation map and precedence
rules are in `docs/README.md`.

## Quick start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
make check
```

The equivalent one-command environment bootstrap is:

```bash
bash scripts/setup_venv.sh
source .venv/bin/activate
```

Run the complete offline release gate before publishing:

```bash
make release-check
```

Heavy and document-generation dependencies are optional:

```bash
python -m pip install -e '.[ml]'         # model-backed experiments
python -m pip install -e '.[schema]'     # schema regeneration
python -m pip install -e '.[documents]'  # DOCX builders
```

## Repository map

```text
src/ask/              maintained Python package
tests/                unit, regression, integration, and release-tooling tests
benchmarks/           frozen diagnostics and external-data contracts
configs/              controller, model, experiment, and release configuration
scripts/              validation, evaluation, analysis, setup, and release CLIs
deploy/               environment-specific GPU, Colab, Ollama, and vLLM wrappers
docs/                 maintained guides, audits, history, and canonical figures
artifacts/            committed machine-readable evidence and manifests
reports/              dated analytical outputs derived from evidence
paper/ and thesis/    publication sources, not runtime package contents
```

See `REPOSITORY_TREE.md` for the release-oriented tree and ownership rules.

## Reproducibility

The offline path requires no secrets or external datasets:

```bash
make repo-check
make test
make lint
make typecheck
make validate-data
make build
```

Use `docs/reproducibility.md` for environment and provenance rules and
`docs/reproduce_results.md` for benchmark-specific commands. Generated runs,
caches, local databases, compiled publications, and handoff ZIPs are ignored and
must not be added back to the source tree.

## Hosted runs

The repository never embeds credentials. Export newly authorized credentials
only in the current shell or a secret manager:

```bash
export OPENROUTER_API_KEY='...'
export LONGMEMEVAL_DATA='/absolute/path/to/the/frozen-input.jsonl'
```

Do not pass secrets as CLI arguments; shell histories and run manifests can
capture them. The active model configuration is
`configs/models/openrouter_qwen_gemma.yaml`.

## Release building

`scripts/release/build_final_release.py` builds the private academic handoff and
a separately sanitized public repository. It reads only Git-tracked public
candidates and refuses a dirty worktree by default:

```bash
python scripts/release/build_final_release.py
```

`--allow-dirty` exists only for local validation builds and should not be used to
publish a release.

## License and security

Code is MIT-licensed. Dataset and annotation terms are documented separately in
`LICENSE-DATA.md`. Never commit credentials, private conversations,
non-redistributable external datasets, participant identities, or local model
stores. See `SECURITY.md` for reporting and release-safety guidance.
