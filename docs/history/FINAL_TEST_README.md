# Final Baseline-Then-Controller Test

Use this package when you want one clean result bundle for the next thesis
decision: first the baselines, then the controller.

## 1. Prepare

In Colab or a GPU shell:

```bash
unzip ksa_controller_final_test_20260612.zip
cd ksa_controller_final_test
KSA_SETUP_OLLAMA=0 bash deploy/colab_prepare.sh
```

`KSA_SETUP_OLLAMA=0` keeps setup focused on the HuggingFace runner. The script
creates `.venv`, installs the package, installs dependencies, and runs tests.

## 2. Run the ordered test

```bash
bash deploy/run_colab_m4w13_serial_final.sh
```

Default behavior:

- runs `b1`, `b2`, `b3`, `b4`, then `controller`
- uses the included 50-session cleaned slice at
  `data/slices/longmemeval_s_cleaned_50_seed0.jsonl`
- fixes `SEED=0`, `N_BOOTSTRAP=1000`, and `PYTHONHASHSEED=0`
- writes outputs to `runs/m4w13_serial_balanced`
- writes `summary.json` and `summary.md`
- fails if any system is incomplete
- creates a result zip after validation

For a higher-recall, slower A10G/A100 pass:

```bash
PROFILE=quality bash deploy/run_colab_m4w13_serial_final.sh
```

To run only one system or a smaller subset:

```bash
bash deploy/run_colab_m4w13_serial_final.sh b1
bash deploy/run_colab_m4w13_serial_final.sh controller
bash deploy/run_colab_m4w13_serial_final.sh b1,controller
```

Subset outputs get separate default directories, for example
`runs/m4w13_serial_balanced_controller`.

## Multi-device runs

Keep these values identical on every device:

```bash
PROFILE=balanced
SEED=0
LIMIT=50
SLICE=data/slices/longmemeval_s_cleaned_50_seed0.jsonl
```

Then split systems across devices:

```bash
bash deploy/run_colab_m4w13_serial_final.sh b1
bash deploy/run_colab_m4w13_serial_final.sh b2
bash deploy/run_colab_m4w13_serial_final.sh b3
bash deploy/run_colab_m4w13_serial_final.sh b4
bash deploy/run_colab_m4w13_serial_final.sh controller
```

To build one table after copying system directories into the same output root:

```bash
python scripts/summarize_m4w13.py runs/m4w13_merged \
  --systems all \
  --json-out runs/m4w13_merged/summary.json \
  --md-out runs/m4w13_merged/summary.md \
  --require-complete
```

For a partial table, use the same command with `--systems b1,controller`.

For a command preview without loading models:

```bash
bash deploy/run_colab_m4w13_serial_final.sh controller --dry-run
```

## 3. Read the decision artifact

Open:

```bash
runs/m4w13_serial_balanced/summary.md
```

Use this order for the next step:

1. Confirm `summary.md` has no missing systems, validation errors, or warnings.
2. Compare controller accuracy and SMRR against `b1`, `b2`, `b3`, and `b4`.
3. If controller improves accuracy but SMRR is high, inspect
   `runs/m4w13_serial_balanced/controller/action_log.jsonl`.
4. If controller loses to `b2` or `b3`, inspect the disagreement rows in
   `answers.jsonl` and `judgments.jsonl` before changing model prompts.

The default same-model judge is useful for iteration, not a final thesis claim.
Use the Ollama-judge path or rejudge completed answers before promoting numbers
to final tables.
