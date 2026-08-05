# Troubleshooting

## Installation and package data

Use Python 3.11 or 3.12 and install from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

If a wheel installation cannot find a default config, schema, or prompt, confirm
that the wheel contains `ask/resources/` and `ask/baselines/prompts/`:

```bash
python -m build
python -m zipfile -l dist/*.whl
```

Do not work around a missing resource with an absolute path. Installed defaults
must resolve through the packaged `ask` resources.

## OpenRouter returns HTTP 401 or 403

- `401` normally indicates a missing or invalid credential.
- `403` with `Access denied by security policy` occurred with the credential
  supplied for the 2026-07-13 audit under default, Venice-only, and
  DeepInfra-only routing. Retrying the same key will not make the run valid.

Create/authorize a replacement key in the account, export it only in the current
shell, and run the two-item smoke before the full evaluation:

```bash
export LONGMEMEVAL_DATA="${PWD}/.private/longmemeval/longmemeval_m_full.jsonl"
bash scripts/evaluation/run_longmemeval_final.sh --smoke
```

Load `OPENROUTER_API_KEY` from the approved secret manager before the smoke run.

Never paste a real key into a config, command history committed to Git, issue,
paper artifact, or review archive. The run wrapper records only key presence.

## OpenRouter returns HTTP 402

HTTP 402 is an account-wide insufficient-credit failure. The client stops
request and shard retries immediately after detecting it; repeated retries
cannot repair the balance. Fund the account, then resume the same immutable run
directory. The recorded V12 policy uses only `google/gemma-4-31b-it` as judge and
has no model fallback. The evaluator records the requested/actual judge,
attempt count, and raw-response hash; the homogeneity verifier rejects any
model substitution or missing provenance.

Do not silently substitute a deterministic score for a failed judge. Such a row
must be marked as a scoring fallback and is ineligible for the homogeneous final
result unless the frozen protocol explicitly permits it.

## Local embedding health returns `Internal Privoxy Error`

This is a loopback-routing problem, not a MiniLM or Qwen failure. On macOS,
Python may inherit the system proxy configuration even when no `HTTP_PROXY`
variable is exported. Final-2.0/V12 explicitly adds loopback hosts to
`NO_PROXY` and uses a proxy-free opener for local health and embedding calls.
Do not resume a final-1.8/V10 directory with the changed frozen code; start the
V12 output directory so the manifest matches the executed implementation.

## LongMemEval data is missing

The dataset is intentionally not shipped. Set `LONGMEMEVAL_DATA` to the exact
frozen 180-item JSONL. The expected slice has 180 unique rows, six competencies
with 30 items each, seed 0, and SHA-256
`f10b4fb4173d3e2d9310d90c2b6bf8f5e7b147cea1d04affa9037b1b9fe6787d`.
The verifier fails closed if the hash, item IDs, or coverage differ.

For an offline command check that needs no data or credential:

```bash
bash scripts/evaluation/run_longmemeval_final.sh --dry-run
```

## A run was interrupted

Resume the same immutable run directory:

```bash
bash scripts/evaluation/run_longmemeval_final.sh --resume
```

Do not combine shards from different configs, models, provider policies, slice
hashes, or judge policies. After completion, run the exact verifier command in
`FINAL_RUN_MATRIX.yaml` and then the judge audit.

## MGP-6 few-shot has only 174 predictions

This is expected for the archived 6-shot run. The release scorer aligns all 180
gold IDs and treats the six missing predictions as `INVALID`, producing a
coverage-aware accuracy of 0.7833 and macro-F1 of 0.7692. The result remains
`incomplete` and must not enter final tables.

## Repository validation reports secrets or absolute paths

Run from an activated development environment:

```bash
make repo-check
```

The validator scans tracked and unignored release candidates, not virtual
environments. It also verifies required paths, release-version consistency, and
the absence of known duplicate canonical datasets. Replace active local paths
with repository-relative paths or `external://` pointers. Historical notes may
describe old locations but must not enter the public release if they expose
private information. Revoke any detected credential; redaction alone does not
make an exposed key safe again.

## Tests need unavailable external services

Tests marked `network`, `external_data`, or `slow` may skip when their explicit
prerequisites are absent. A skip is acceptable only when its reason is printed.
The default unit suite, repository validator, schema validation, lint, type
check, build, and offline smoke must still pass.
