# Colab T4 MGP-6 Rerun Runbook

This kit runs the repaired MGP-6 evaluation, lineage/SMRR metrics, RC@C replay,
and the promotion gate check. It does not need LongMemEval-S.

## 1. Upload And Unzip

In a Colab notebook with a T4 runtime:

```python
from google.colab import files
uploaded = files.upload()
```

Upload the `ask_controller_mgp6_t4_colab_*.zip` file, then run:

```bash
!unzip -q ask_controller_mgp6_t4_colab_*.zip
%cd ask_controller_mgp6_t4_colab
```

## 2. Practical T4 Run

This uses the T4-safe model profile:

- extractor: `llama3.2:3b`
- classifier: `phi3.5:3.8b`
- output: development tier, not final thesis evidence

```bash
!PROFILE=t4 bash deploy/run_colab_mgp6_t4.sh
```

The script prints `RESULT_ZIP=/content/...zip` at the end.

## 3. Promotion-Eligible Run

The promotion gate only accepts the proposal-spec model profile:

- extractor/classifier: `llama3:8b`
- output: `final-candidate` tier if the run completes and sanity passes

On T4 this is slower, but it is the path to a citable artifact:

```bash
!PROFILE=thesis OUT=runs/m4w14_thesis RC_OUT=runs/m4w15_thesis \
  RESULT_ZIP=/content/ask_mgp6_thesis_results.zip \
  bash deploy/run_colab_mgp6_t4.sh
```

To make Colab exit non-zero when the promotion gate fails:

```bash
!PROFILE=thesis REQUIRE_PROMOTION=1 bash deploy/run_colab_mgp6_t4.sh
```

## 4. Download Results

Use the exact `RESULT_ZIP` path printed by the script:

```python
from google.colab import files
files.download("/content/ask_mgp6_thesis_results.zip")
```

If you used the default practical run, the filename starts with
`/content/ask_mgp6_t4_results_`.

## 5. Useful Overrides

```bash
# Skip tests to save time.
!ASK_RUN_TESTS=0 PROFILE=t4 bash deploy/run_colab_mgp6_t4.sh

# Keep artifacts even if sanity warnings fire.
!FAIL_ON_SANITY=0 PROFILE=t4 bash deploy/run_colab_mgp6_t4.sh

# Reuse already-pulled Ollama models.
!ASK_PULL_MODELS=0 PROFILE=t4 bash deploy/run_colab_mgp6_t4.sh
```

## 6. What To Send Back

Send the result zip printed by the script. It includes:

- `runs/m4w14_<profile>/`
- `runs/m4w15_<profile>/`
- `promotion_gate.txt`
- generated `NOTES/m4w14_mgp6_results.md`
- active config and prompt files
