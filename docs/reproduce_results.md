# Reproduce Results

## Environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e '.[dev]'
python -m pytest -q
ruff check .
```

Observed on 2026-07-07:

- `python -m pytest -q`: 381 passed, 5 skipped
- `python -m pytest -q -p no:cov`: 381 passed, 5 skipped
- `ruff check .`: All checks passed

Install `.[ml]` only for model-backed benchmark runs.

## Accepted MGP-6 Evidence

Valid run: `runs/m4w14_thesis_colab_20260608`.

Report files:

- `runs/m4w14_thesis_colab_20260608/controller/mgp6_report.json`
- `runs/m4w14_thesis_colab_20260608/b4/mgp6_report.json`
- `runs/m4w14_thesis_colab_20260608/recoverability_report.json`
- `runs/m4w14_thesis_colab_20260608/smrr_report.json`

Summary:

- controller action accuracy: 0.617
- naive-overwrite action accuracy: 0.517
- paired CI on the difference includes 0
- lineage recoverability: controller 1.0 vs naive-overwrite 0.0

Invalid runs retained for provenance only:

- `runs/m4w14`
- `runs/m4w15`

Reason: invalid pre-fix runs; extraction bug caused 46/60 scenarios to be lost.

## RC@C

Valid replay: `runs/m4w15_thesis_colab_20260608`.

Regeneration command:

```bash
source .venv/bin/activate
python scripts/evaluate_rc_at_c_mgp6.py \
  --run-root runs/m4w14_thesis_colab_20260608 \
  --out runs/m4w15_thesis_colab_20260608 \
  --n-bootstrap 1000 \
  --seed 0
```

The regenerated metric sweep matched the existing `rc_at_c_sweep.csv`; metadata
timestamps were refreshed.

## LongMemEval-S 50

Accepted partial evidence:

- B1 no-memory: `artifacts/m4w13_50_llama/runs(2).zip`, 18%
- B2 flat-vector: `artifacts/m4w13_50_llama/runs(2).zip`, 38%
- B3 recency: `artifacts/m4w13_50_llama/runs(3).zip`, 22%

B4 naive-overwrite and controller are missing. See `LONGMEMEVAL_B4_TODO.md` for
the exact continuation command and required inputs.
