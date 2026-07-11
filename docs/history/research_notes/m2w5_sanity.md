# M2-W5 Sanity Note

## Holdout-10

Run command:

```bash
source .venv/bin/activate
python scripts/run_extraction.py --input data/dev/extraction_holdout10_seed0.jsonl \
  --prompt prompts/extraction_v_final.j2 \
  --out runs/m2w5/holdout10/extractions.jsonl \
  --trace runs/m2w5/holdout10/trace.jsonl --ollama-model llama3.2:3b \
  --seed 0 --temperature 0.0 --max-new-tokens 256 --num-ctx 4096
```

Result: 10 rows, 10 extracted items, 0 schema violations.

Failure-mode tally:

| class | count |
|---|---:|
| correct | 10 |
| over-extracted | 0 |
| under-extracted | 0 |
| type-error | 0 |
| schema-violation | 0 |
| marker-error | 0 |

The holdout is disjoint from dev-30 but shares the same synthetic limitation:
all rows are stable coffee-preference assertions. It checks prompt plumbing and
gross overfitting, not real stratified generalization.

## Smoke Pipeline

Run command:

```bash
source .venv/bin/activate
python scripts/smoke_extraction_pipeline.py \
  --extractions runs/m2w5/v_final/extractions.jsonl \
  --out-dir runs/m2w5/smoke
```

Result: inserted 30 rows into `runs/m2w5/smoke/extraction_smoke.sqlite` and
wrote `runs/m2w5/smoke/action_log.jsonl`.
