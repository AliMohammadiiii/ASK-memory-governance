# Controller forensic debug kit (2026-05-30)

Two files. Unzip at the repo root (`ksa_controller/`); paths are preserved.

- `scripts/debug_controller_trace.py` — one-command diagnostic over a finished run.
- `tests/test_extraction_conf0_kept.py` — regression test (model-free).

## 1. Confirm the regression test is green

```bash
cd ksa_controller
source .venv/bin/activate            # or your env
python -m pytest tests/test_extraction_conf0_kept.py -q
```

## 2. Re-run the smoke WITH traces enabled, then diagnose

The diagnostic reads the per-stage trace files. They are written automatically
when `--out` is set. Re-run your smoke (controller only is fine):

```bash
python scripts/run_m4w13_ollama.py --model-profile thesis \
  --slice data/slices/longmemeval_s_cleaned_50_seed0.jsonl \
  --out runs/m4w13_smoke10 --systems controller --limit 10 \
  --seed 0 --n-bootstrap 1000 \
  --embedder-backend sentence_transformer --embedder-model all-minilm:l6-v2 \
  --ollama-host http://127.0.0.1:11434 --ollama-timeout-s 900 --judge-timeout-s 900
```

Then run the diagnostic and capture stdout:

```bash
python scripts/debug_controller_trace.py runs/m4w13_smoke10/controller --n 8 \
  | tee /content/controller_forensics.txt
```

## 3. Send me back

Just the stdout (`controller_forensics.txt`). It already contains:

- EXTRACTION: empty-rate, items/call, confidence histogram, and an
  **OVER-EXTRACTION** count of question/request-shaped items (the conf=0.0
  junk-paraphrase risk we flagged).
- RELATION: stage-1 label mix, final relation mix, supersede-eligible count
  (explains `Supersede=0`).
- ACTIONS: action distribution + how many KEEP-with-prior candidates were
  dropped (the silent memory-loss path).
- QA FAILURES: taxonomy (Unknown vs partial-precision vs wrong) + per-example
  trace (gold, predicted, judge rationale, retrieved sessions).

If `relation_trace.jsonl` is absent it means no priors were found — expected,
and itself the reason SUPERSEDE cannot fire on LongMemEval.

The raw `*.jsonl` files are NOT required, but if you want a deeper look send
`runs/m4w13_smoke10/controller/{extraction_trace,relation_trace,action_log,
judgments,predictions}.jsonl`.

## Note

This kit does not change any pipeline behavior. It only adds a read-only
diagnostic and a regression test. No thresholds, top-k, model sizes, or
concurrency were touched.
