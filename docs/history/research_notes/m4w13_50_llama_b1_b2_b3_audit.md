# M4-W13 50-Item Llama B1/B2/B3 Audit

Status date: 2026-06-02

Source artifacts:

- `artifacts/m4w13_50_llama/runs(2).zip` for `b1` and `b2`
- `artifacts/m4w13_50_llama/runs(3).zip` for `b3`

Run root inside artifacts: `runs/m4w13_50_llama/`

## Zip Artifact Inventory

| Zip | Size | SHA-256 | File count | Root manifest | Accepted contents |
|---|---:|---|---:|---|---|
| `artifacts/m4w13_50_llama/runs(2).zip` | 558269 bytes | `72c8656b96f140422b73aaeb150f15e191419eeff6423cb5b5a25be4cac680bb` | 51 files | `systems=["b3"]`, `complete=false`, `tier=final-candidate` | `b1`, `b2` only |
| `artifacts/m4w13_50_llama/runs(3).zip` | 4154287 bytes | `3d635ccbc94652706c489df4141dceff4d6f44d095e4e22d3a023137101c4fc5` | 27 files | `systems=["b3"]`, `complete=true`, `tier=final-candidate` | `b3` |

`runs(2).zip` includes an incomplete B3 attempt in addition to the accepted B1
and B2 directories. The accepted B3 directory is from `runs(3).zip`.

## Scope

This note audits only the completed baseline directories:

- `b1` = no-memory
- `b2` = flat-vector
- `b3` = recency-pruning

`runs(2).zip` also contains an incomplete `b3` attempt. The accepted B3 result
comes from `runs(3).zip`, which contains only B3. Neither zip should be treated
as a complete all-system M4-W13 result.

The pasted terminal log starts with a failed `cd ksa_gpu_run_package/ksa_controller`
line for the B1/B2 run. This audit is based on the produced zip artifacts and
their internal reports/JSONL files; the failed pre-run `cd` line does not
invalidate the completed outputs.

## Protocol Evidence

- Dataset/slice: `data/slices/longmemeval_s_cleaned_50_seed0.jsonl`
- Slice type: real cleaned LongMemEval-S 50-item slice, not synthetic
- Model profile in artifact manifest: `thesis`
- Answerer: `llama3:8b`
- Judge: Ollama `phi3.5:3.8b`
- Embedding backend: `sentence_transformer`
- Bootstrap samples: `1000`
- Seed: `0`
- `runs(2).zip` root manifest status: `complete=false` because the later `b3`
  attempt in that zip was incomplete.
- `runs(3).zip` root manifest status: `complete=true` for `systems=["b3"]`.

## Validation Checks

Validated from the zip artifacts without rerunning inference or judging.

- `m4w13_validation.validate_run_dir(..., expected_rows=50)` passed for
  `b1`, `b2`, and `b3`.
- `answers.jsonl`, `predictions.jsonl`, and `judgments.jsonl` each contain 50
  non-empty rows for all three systems.
- `b3/action_log.jsonl` contains 1372 rows and `b3/extraction_trace.jsonl`
  contains 1600 rows.
- `session_id` coverage is 50 unique IDs for all three systems.
- `answers.jsonl`, `predictions.jsonl`, and `judgments.jsonl` cover the same
  session IDs for each accepted system.
- Computed accuracy from `judgments.jsonl` exactly matches `report.json`.
- Judge fallback count is zero: `used_fallback=false` for all 150 B1/B2/B3
  judgments.
- No empty prediction text or empty judged prediction was found.
- B3 current-session leakage count is zero.

## Results

| System | Baseline | n | Correct | Accuracy | 95% CI | Decision |
|---|---|---:|---:|---:|---|---|
| B1 | no-memory | 50 | 9 | 18.0% | 8.0%-30.0% | accepted |
| B2 | flat-vector | 50 | 19 | 38.0% | 24.0%-52.0% | accepted |
| B3 | recency | 50 | 11 | 22.0% | 10.0%-34.0% | accepted |

Per-competency accuracy:

| Competency | B1 | B2 | B3 |
|---|---:|---:|---:|
| knowledge-update | 2/12 = 16.7% | 4/12 = 33.3% | 4/12 = 33.3% |
| multi-session | 3/12 = 25.0% | 4/12 = 33.3% | 3/12 = 25.0% |
| single-session-assistant | 2/5 = 40.0% | 3/5 = 60.0% | 0/5 = 0.0% |
| single-session-preference | 1/3 = 33.3% | 1/3 = 33.3% | 1/3 = 33.3% |
| single-session-user | 0/6 = 0.0% | 3/6 = 50.0% | 1/6 = 16.7% |
| temporal-reasoning | 1/12 = 8.3% | 4/12 = 33.3% | 2/12 = 16.7% |

## Decision

The B1, B2, and B3 artifacts are complete and internally consistent. Do not
rerun `b1`, `b2`, or `b3` for the `runs/m4w13_50_llama` protocol unless the
evaluation protocol changes.

Remaining systems for the same all-system comparison are `b4` and
`controller`.

When continuing the Ollama thesis run, keep the accepted
`runs/m4w13_50_llama/b1`, `runs/m4w13_50_llama/b2`, and
`runs/m4w13_50_llama/b3` directories from these artifacts and run only:

```bash
python scripts/run_m4w13_ollama.py \
  --model-profile thesis \
  --slice data/slices/longmemeval_s_cleaned_50_seed0.jsonl \
  --out runs/m4w13_50_llama \
  --systems b4,controller \
  --seed 0 \
  --n-bootstrap 1000 \
  --embedder-backend sentence_transformer \
  --controller-include-assistant-context \
  --session-workers 2 \
  --ollama-host http://127.0.0.1:11434 \
  --ollama-timeout-s 1800 \
  --judge-timeout-s 1800
```

Do not use a single zip-level manifest alone as the all-system completion
signal; `runs(2).zip` correctly says `complete=false`, while `runs(3).zip` says
`complete=true` only for `systems=["b3"]`.
