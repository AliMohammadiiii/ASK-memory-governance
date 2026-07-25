# Colab Run Kit

This package is intentionally small. It does not include
`longmemeval_s_cleaned.json`; download it inside Colab from Hugging Face.

## Setup

```bash
unzip ask_controller_colab_kit.zip
cd ask_controller_colab_kit
bash deploy/colab_prepare.sh
```

If you install manually in notebook cells instead of using
`deploy/colab_prepare.sh`, keep setuptools below 82 because recent Colab torch
builds declare `setuptools<82`:

```bash
python -m pip install -q --upgrade pip wheel "setuptools<82"
python -m pip install -q -e .
python -m pip install -q -r deploy/colab_requirements.txt
```

The setup script:

- creates `.venv`
- installs Python dependencies
- installs and starts Ollama
- pulls `llama3.2:3b`, `phi3.5:3.8b`, `qwen3.5:9b`, and `phi4:14b`
- downloads `/content/longmemeval/longmemeval_s_cleaned.json`
- runs the test suite

For HF-only iteration, you can skip the Ollama install and model pulls:

```bash
ASK_SETUP_OLLAMA=0 bash deploy/colab_prepare.sh
```

## Final Ordered Test Bundle

When you need the clean baseline-first result bundle, run the serial wrapper:

```bash
bash deploy/run_colab_m4w13_serial_final.sh
```

It runs `b1`, `b2`, `b3`, `b4`, then `controller`, validates completeness with
`scripts/summarize_m4w13.py --require-complete`, writes `summary.json` and
`summary.md`, and creates the result zip. The default slice is the included
50-session cleaned slice at `data/slices/longmemeval_s_cleaned_50_seed0.jsonl`.
The wrapper fixes `SEED=0`, `N_BOOTSTRAP=1000`, and `PYTHONHASHSEED=0` unless
you deliberately override them.

You can select one system or a subset directly:

```bash
bash deploy/run_colab_m4w13_serial_final.sh b1
bash deploy/run_colab_m4w13_serial_final.sh controller
bash deploy/run_colab_m4w13_serial_final.sh b1,controller
```

For multi-device runs, keep `PROFILE`, `SEED`, `LIMIT`, and `SLICE` identical
on every device. After copying the system directories into one output root, run:

```bash
python scripts/summarize_m4w13.py runs/m4w13_merged \
  --systems all \
  --json-out runs/m4w13_merged/summary.json \
  --md-out runs/m4w13_merged/summary.md \
  --require-complete
```

Use the slower quality profile only after the balanced run produces a complete
table:

```bash
PROFILE=quality bash deploy/run_colab_m4w13_serial_final.sh
```

## M4-W13 50-Session Cache Run

For the current cleaned 50-session package run, prefer the dedicated runbook:

```bash
less deploy/COLAB_M4W13_50_RUNBOOK.md
```

The one-command path for a complete resumable controller + baseline bundle is:

```bash
PROFILE=balanced SYSTEMS=all OUT=runs/m4w13_50_balanced \
  bash deploy/run_colab_m4w13_50_cache.sh
```

It validates `b1`, `b2`, `b3`, `b4`, and `controller`, writes `summary.json`
and `summary.md`, and zips the full output directory. Re-run the same command
with the same `OUT` to skip completed systems and resume incomplete ones.

## Smoke Run

```bash
source .venv/bin/activate
python scripts/run_m4w13_ollama.py \
  --model-profile light \
  --limit 2 \
  --slice /content/longmemeval/longmemeval_s_cleaned.json \
  --out runs/m4w13_light_smoke \
  --ollama-host http://127.0.0.1:11434 \
  --ollama-timeout-s 1800 \
  --judge-timeout-s 1800 \
  --embedder-backend ollama
```

## Final M4-W13 Run

```bash
bash deploy/run_colab_m4w13_light.sh
```

The default Colab profile is `t4`: `qwen3.5:9b` for answering, `llama3.2:3b`
for extraction/retrieval embeddings, and `phi3.5:3.8b` for judging and
classification. This avoids T4 model swapping and uses the models that reliably
emit structured JSON. To fall
back to the smaller profile:

```bash
MODEL_PROFILE=light bash deploy/run_colab_m4w13_light.sh
```

## Fast HF Controller Run

For speed-focused controller iteration, run Transformers directly in Python
instead of routing every small call through Ollama:

```bash
bash deploy/run_colab_m4w13_hf_controller.sh
```

This shares `Qwen/Qwen2.5-3B-Instruct` across answerer, extractor, classifier,
and judge. The sentence-transformer embedder defaults to `auto`: it uses CUDA
only when the installed torch build reports CUDA is available, otherwise it
falls back to CPU instead of crashing. It enables top-k fast mode for `b3`,
`b4`, and `controller`, so the
runner embeds all allowed `haystack_sessions` turns first and only sends the top
32 user turns through LLM extraction. This should be much faster than full
ingestion and avoids Ollama model swaps. The runner also caps structured
extraction/relation output at 192/96 new tokens. The default same-model judge is
for iteration. The runner also enables raw-turn fallback for B3 and the
controller-style systems, so selected turns with empty extraction are indexed as
raw episodic memories; this is an approximate recall-focused mode for small
local HF extractors. Neighbor expansion is off by default
(`--controller-retrieval-neighbor-window 0`) because it increases prompt size
and can add distractors; enable it only for targeted multi-turn diagnostics.
Keep the Ollama `phi3.5:3.8b` judged path for final comparable numbers. The
first HF run still has to download the model from Hugging Face.

The A10G controller-only wrapper is the exception: it defaults the neighbor
window to `2`. That profile already limits extraction to 8 selected user turns,
so the neighbor window adds nearby raw haystack turns only at answer-prompt time
without triggering more extractor/classifier calls.

If you want HF generation but the old Ollama judge, start Ollama and pass:

```bash
python scripts/run_m4w13_hf.py \
  --systems controller \
  --limit 35 \
  --slice /content/longmemeval/longmemeval_s_cleaned.json \
  --out runs/m4w13_hf_ollama_judge \
  --controller-memory-top-k 32 \
  --judge-backend ollama \
  --judge-model phi3.5:3.8b \
  --ollama-host http://127.0.0.1:11434
```

## A100 Parallel HF Run

On an A100 runtime, run all five systems concurrently with 50 sessions each:

```bash
ASK_SETUP_OLLAMA=0 bash deploy/colab_prepare.sh
bash deploy/run_colab_m4w13_hf_a100_parallel.sh
```

The A100 runner starts one subprocess per system (`b1`, `b2`, `b3`, `b4`,
`controller`), writes logs under `runs/m4w13_a100_50/_logs`, then runs
`scripts/summarize_m4w13.py --require-complete` and zips the result directory.
It streams each subprocess line to notebook output with a system prefix, emits
row-count heartbeats every 30 seconds, and keeps the full prepare log under
`/content/ask_logs`. It checks that CUDA is available and that the visible GPU
is an A100. The default is `MAX_WORKERS=2`, which is the conservative A100 40GB
setting for 7B fp16 model copies. Raise it only after checking free VRAM, for
example:

```bash
MAX_WORKERS=3 bash deploy/run_colab_m4w13_hf_a100_parallel.sh
```

The runner is resumable. If the notebook is interrupted before all systems
write `report.json`, rerun the same command with the same `OUT`; completed
session rows in `answers.jsonl` and `judgments.jsonl` are kept and only missing
sessions are evaluated.

For a cheaper decision run, use:

```bash
bash deploy/run_colab_m4w13_hf_a100_budget.sh
```

This budget profile runs only `b1,b2,controller`, uses at most two workers, sets
`CONTROLLER_MEMORY_TOP_K=12`, and caps structured outputs at 128/64 tokens. It
skips only systems whose report, row counts, and command fingerprint match the
requested run, so you can stop an expensive run and resume the useful subset in
the same output directory:

```bash
OUT=runs/m4w13_a100_50 SYSTEMS=b1,b2,controller bash deploy/run_colab_m4w13_hf_a100_budget.sh
```

Use `SYSTEMS=all` only when you need the expensive `b3` and `b4` ablations.

For the first pass on an A10G, run only the controller:

```bash
bash deploy/run_colab_m4w13_hf_a10g_controller.sh
```

This wrapper passes `--no-require-a100`, uses one worker, sets
`CONTROLLER_MEMORY_TOP_K=8`, sets `CONTROLLER_RETRIEVAL_NEIGHBOR_WINDOW=2`,
and writes to `runs/m4w13_a10g_controller_50`.
If you also want the cheap B1 reference, run:

```bash
SYSTEMS=b1,controller bash deploy/run_colab_m4w13_hf_a10g_controller.sh
```

For score tuning on an A10G, use the staged sweep driver instead of changing
one knob at a time:

```bash
python scripts/run_m4w13_a10g_sweep.py \
  --stage pilot \
  --slice /content/longmemeval/longmemeval_s_cleaned.json

python scripts/run_m4w13_a10g_sweep.py \
  --stage confirm \
  --slice /content/longmemeval/longmemeval_s_cleaned.json

python scripts/run_m4w13_a10g_sweep.py \
  --stage final \
  --slice /content/longmemeval/longmemeval_s_cleaned.json
```

`pilot` runs six controller configs on 12 sessions, `confirm` runs the top two
configs on all 50 sessions, and `final` runs `b1,b2,b3,b4,controller` serially
with the best confirmed config. After an HF run completes, get comparable judge
numbers without regenerating answers:

```bash
python scripts/rejudge.py \
  --run runs/m4w13_a10g_sweep/final/<config>/controller \
  --slice /content/longmemeval/longmemeval_s_cleaned.json \
  --judge-backend ollama \
  --judge-model phi3.5:3.8b
```

`b3`, `b4`, and `controller` print heartbeat lines by default while they ingest
memory sessions and extract turns. B4/controller also cache extractor outputs
within the run, so later questions should avoid repeating extractor calls for
already-seen haystack turns. Cache files are persisted in the output directory,
and trace files from a failed run are imported on restart. If a run appears
idle, check whether these files are growing before interrupting it:

```bash
wc -l runs/m4w13_a100_50/b3/{extraction_trace.jsonl,action_log.jsonl,answers.jsonl,judgments.jsonl} 2>/dev/null || true
wc -l runs/m4w13_a100_50/controller/{extraction_trace.jsonl,relation_trace.jsonl,action_log.jsonl,answers.jsonl,judgments.jsonl} 2>/dev/null || true
tail -n 120 runs/m4w13_a100_50/_logs/b3.log
```

## Parallel M4-W13 Runs

Run one system per Colab runtime. Default profile is `t4`:

```bash
bash deploy/run_colab_m4w13_one_system.sh b1
bash deploy/run_colab_m4w13_one_system.sh b2
bash deploy/run_colab_m4w13_one_system.sh b3
bash deploy/run_colab_m4w13_one_system.sh b4
bash deploy/run_colab_m4w13_one_system.sh controller
```

Each runtime writes `/content/m4w13_<system>_*.zip`. Copy those zips into one
Colab, unzip all of them into the same project directory, then run:

```bash
python scripts/summarize_m4w13.py runs/m4w13 \
  --json-out runs/m4w13/summary.json \
  --md-out runs/m4w13/summary.md \
  --require-complete
zip -r /content/m4w13_merged_results.zip runs/m4w13
```

`--require-complete` makes this merge step fail unless all five report
directories are present: `b1`, `b2`, `b3`, `b4`, and `controller`.

## Full M4-W13 to M4-W16 Chain

This is much longer because M4-W15 runs a 21-point threshold sweep.

```bash
bash deploy/run_colab_full_m4_light.sh
```

## Save Results to Google Drive

```python
from google.colab import drive
drive.mount("/content/drive")
```

```bash
cp /content/m4w13_results_*.zip /content/drive/MyDrive/
# or, after the full chain:
cp /content/m4_full_results_*.zip /content/drive/MyDrive/
```
