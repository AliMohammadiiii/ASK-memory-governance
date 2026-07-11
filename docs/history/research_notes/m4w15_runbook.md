# M4-W15 RC@C and Main Table Runbook

Status update 2026-07-07: the historical `runs/m4w15/` path is invalid because
it was replayed from the invalid pre-fix `runs/m4w14/` action logs. The valid
post-fix RC@C artifact is `runs/m4w15_thesis_colab_20260608/`, replayed from
`runs/m4w14_thesis_colab_20260608/`.

The original runbook below is retained as historical tooling context only.

Run the prerequisite real-Ollama evaluations first:

```bash
source .venv/bin/activate
python scripts/run_m4w13_ollama.py --model-profile light --slice /Users/ali/Downloads/longmemeval/longmemeval_s_cleaned.json
python scripts/run_mgp6.py --model-profile light --systems all --out runs/m4w14
```

Then run the 21-point controller threshold sweep and assemble the deliverables:

```bash
source .venv/bin/activate
python scripts/run_m4w15.py --model-profile light --longmemeval-slice /Users/ali/Downloads/longmemeval/longmemeval_s_cleaned.json
```

The light profile uses `llama3.2:3b` for answer/extraction/retrieval embeddings
and `phi3.5:3.8b` for judge/classification. LongMemEval retrieval embeddings
use Ollama `/api/embed` by default.

The repository-local `data/longmemeval_s_synthetic.jsonl` is only suitable for
smoke checks. `scripts/run_m4w15.py` refuses to create acceptance artifacts from
that path unless `--allow-synthetic-longmemeval` is passed explicitly.
For real-data smoke tests, use
`data/slices/longmemeval_s_cleaned_50_seed0.jsonl`.

Expected acceptance outputs after a fresh full run:

- `runs/m4w15_thesis_colab_20260608/rc_at_c_curve.png`
- `runs/m4w15_thesis_colab_20260608/rc_at_c_curve.pdf`
- `runs/m4w15_thesis_colab_20260608/rc_at_c_report.json`
- `runs/m4w15_thesis_colab_20260608/rc_at_c_sweep.csv`
- `<fresh-m4w15-run>/main_table.csv`
- `NOTES/m4w15_main_table.md`

For a no-write check of the exact commands:

```bash
source .venv/bin/activate
python scripts/run_m4w15.py --dry-run
```
