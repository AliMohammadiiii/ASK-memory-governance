# M4 Judge Substitution

Date: 2026-05-21

## Decision

M4-W13 uses an explicit judge backend instead of the implicit M1 self-judge.
The backend is configured through `src/ksa/eval/judge.py` and surfaced in
`scripts/run_baseline.py` via:

```bash
--judge-backend ollama --judge-model phi4:14b
```

The local Ollama model pool available for this run is:

- `gemma4:e4b`
- `gemma4:e2b`
- `qwen3.5:9b`
- `llama3.2:3b`
- `phi3.5:3.8b`
- `phi4:14b`

Default role assignment is recorded in `configs/m4w13-ollama.yaml`:

| Role | Model |
|---|---|
| Answer generation | `gemma4:e4b` |
| B3 M2 extractor | `llama3.2:3b` |
| B4/controller extractor | `llama3.2:3b` |
| B4/controller relation classifier | `phi3.5:3.8b` |
| Substituted judge | `phi4:14b` |

The judge asks Ollama for JSON-formatted output and uses the same LongMemEval
binary rubric in `src/ksa/eval/longmemeval.py`.

## Determinism Check

The runner preserves deterministic settings: `temperature=0.0` and fixed
`--seed`. A 10-question determinism sanity should be run before the full
M4-W13 job with the final dataset path:

```bash
source .venv/bin/activate

python scripts/run_baseline.py --baseline no_memory \
  --slice <real-longmemeval-s.jsonl> --out runs/m4w13_judge_sanity/seed0 \
  --seed 0 --limit 10 --n-bootstrap 10 \
  --ollama --ollama-model gemma4:e4b \
  --judge-backend ollama --judge-model phi4:14b

python scripts/run_baseline.py --baseline no_memory \
  --slice <real-longmemeval-s.jsonl> --out runs/m4w13_judge_sanity/seed1 \
  --seed 1 --limit 10 --n-bootstrap 10 \
  --ollama --ollama-model gemma4:e4b \
  --judge-backend ollama --judge-model phi4:14b
```

Compare the two `judgments.jsonl` files on `(session_id, correct,
judge_rationale)`. Any mismatch blocks the full run until investigated.

## Cost

No API cost is incurred when using the local Ollama substitute judge. Wall-clock
cost is tracked by `report.json` per system and summarized by
`scripts/summarize_m4w13.py`.

## Publication Caveat

The repository currently contains `data/longmemeval_s_synthetic.jsonl`, not the
real LongMemEval-S release file. Runs against the synthetic file validate the
pipeline only; they are not Chapter 4 publication numbers.
