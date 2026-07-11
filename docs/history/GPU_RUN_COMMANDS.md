# GPU Run Commands

Purpose: run the remaining GPU-side LongMemEval-S evaluation and send back the
result bundle. The current package already includes completed M4-W14 MGP-6 and
M4-W15 RC@C final-candidate artifacts.

## 1. Unpack And Setup

```bash
unzip ksa_gpu_run_package_2026-05-29.zip
cd ksa_gpu_run_package_2026-05-29/ksa_controller
```

For Colab or a fresh Linux GPU box:

```bash
bash deploy/colab_prepare.sh
source .venv/bin/activate
```

If you already have Python/Ollama installed and do not want the Colab setup:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e '.[dev,ml]'
python -m pytest -q
```

## 2. Recommended Final-Candidate LongMemEval-S Run

For the current 50-session cleaned slice, the most practical path is the
resumable cache runner. It runs all LongMemEval systems into one output root,
validates the artifacts, and zips the data bundle so completed baselines do not
need to be regenerated:

```bash
source .venv/bin/activate
PROFILE=balanced SYSTEMS=all OUT=runs/m4w13_50_balanced \
  bash deploy/run_colab_m4w13_50_cache.sh
```

Use `PROFILE=quality` when accuracy matters more than wall-clock time. It runs
serially with the 7B quality preset:

```bash
source .venv/bin/activate
PROFILE=quality SYSTEMS=all OUT=runs/m4w13_50_quality \
  bash deploy/run_colab_m4w13_50_cache.sh
```

See `deploy/COLAB_M4W13_50_RUNBOOK.md` for notebook cells and controller-only
A10G/A100 variants.

## 3. Faster A100/A10G Diagnostic Path

Use this only for speed-focused diagnostics. Same-model/HF judged runs remain
pilot evidence unless rejudged.

```bash
source .venv/bin/activate
KSA_SETUP_OLLAMA=0 bash deploy/colab_prepare.sh
bash deploy/run_colab_m4w13_hf_a100_parallel.sh
```

For A10G controller plus no-memory reference:

```bash
source .venv/bin/activate
SYSTEMS=b1,controller bash deploy/run_colab_m4w13_hf_a10g_controller.sh
```

After any HF run, rejudge completed answers with Ollama before treating them as
comparable evidence:

```bash
python scripts/rejudge.py \
  --run runs/m4w13_a100_50/controller \
  --slice /content/longmemeval/longmemeval_s_cleaned.json \
  --judge-backend ollama \
  --judge-model phi3.5:3.8b
```

## 4. Summarize And Validate

For the clean final-candidate output:

```bash
python scripts/summarize_m4w13.py runs/m4w13_final_candidate \
  --json-out runs/m4w13_final_candidate/summary.json \
  --md-out runs/m4w13_final_candidate/summary.md \
  --require-complete
```

Keep M4-W14/M4-W15 artifacts as already provided unless you intentionally want
to reproduce them:

```bash
python scripts/run_mgp6.py \
  --input data/mgp6_v1_seed0.jsonl \
  --out runs/m4w14_gpu_repro \
  --systems all \
  --model-profile light \
  --seed 0 \
  --n-bootstrap 1000 \
  --scorecard-config configs/controller_active.yaml

python scripts/evaluate_smrr_mgp6.py \
  --mgp6 data/mgp6_v1_seed0.jsonl \
  --run-root runs/m4w14_gpu_repro \
  --out runs/m4w14_gpu_repro/smrr_report.json \
  --csv runs/m4w14_gpu_repro/smrr_table.csv

python scripts/evaluate_rc_at_c_mgp6.py \
  --mgp6 data/mgp6_v1_seed0.jsonl \
  --run-root runs/m4w14_gpu_repro \
  --out runs/m4w15_gpu_repro
```

## 5. Zip Results To Send Back

Run this from `ksa_controller`:

```bash
RESULT_ZIP="/content/ksa_gpu_results_$(date +%Y%m%d_%H%M%S).zip"
zip -r "$RESULT_ZIP" \
  ARTIFACT_MANIFEST.md \
  README.md \
  configs \
  NOTES/m4w13_final_policy.md \
  NOTES/m4w14_mgp6_results.md \
  runs/m4w13_final_candidate \
  runs/m4w13_a100_50 \
  runs/m4w13_a10g_controller_50 \
  runs/m4w13_a10g_sweep \
  runs/m4w14 \
  runs/m4w15 \
  -x '*/__pycache__/*' '*.pyc' '*/.DS_Store'

echo "$RESULT_ZIP"
```

Send that zip back.
