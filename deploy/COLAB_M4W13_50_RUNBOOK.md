# M4-W13 50-Session Colab Runbook

This runbook is for the cleaned LongMemEval-S 50 slice shipped in the package.
It runs the controller and baselines into one resumable output root, validates
row counts/artifacts, and zips the complete data bundle so the baselines do not
need to be paid for again.

## Recommended Infrastructure

Use a dedicated A100 runtime when you need the full `b1,b2,b3,b4,controller`
bundle. Colab A100 is fine if it is actually allocated, but it is not a
guaranteed resource. If Colab cannot allocate A100, rent a single A100 80GB and
run the `balanced` profile first.

Profiles:

| Profile | Best for | Model | Workers | Notes |
|---|---|---|---:|---|
| `balanced` | Best cost/time tradeoff for complete 50-session output | `Qwen/Qwen2.5-3B-Instruct` | 5 on A100 | Runs all systems concurrently, validates, zips. |
| `quality` | Accuracy-first controller/baseline evidence when time matters less | `Qwen/Qwen2.5-7B-Instruct` | 1 | Serial by design; also works for controller-only on A10G/A100. |

## Cell 1 - Unpack And Enter The Latest Package

```python
!rm -rf /content/ksa_gpu_run_package
!unzip -q /content/ksa_gpu_run_package_allfixes_v4_tradeoff_20260602.zip -d /content
%cd /content/ksa_gpu_run_package/ksa_controller
```

If you are using a differently named zip, replace only the zip filename. Keep
the `%cd` line; a shell `!cd ...` does not persist between notebook cells.

## Cell 2 - Install Dependencies

```python
!KSA_SETUP_OLLAMA=0 KSA_RUN_TESTS=0 bash deploy/colab_prepare.sh
!source .venv/bin/activate && python -m pip install --upgrade pip wheel "setuptools<82"
!source .venv/bin/activate && python -m pip install -e .
!source .venv/bin/activate && python -m pip install -r deploy/colab_requirements.txt
!source .venv/bin/activate && python -m pip install "faiss-cpu>=1.8,<2" "sentence-transformers>=3.0,<4"
```

## Cell 3 - Fast Contract Tests

```python
!source .venv/bin/activate && python -m pytest \
  tests/test_extraction_repair_regression.py \
  tests/test_extraction_conf0_kept.py \
  tests/test_recoverability.py \
  tests/test_run_sanity.py \
  tests/test_classifier_schema_normalization.py \
  tests/test_m4w13_hf_runner.py \
  tests/test_m4w13_validation.py \
  -q
```

## Cell 4 - Best Tradeoff Full Bundle

This is the default path for getting controller plus all baselines once:

```python
!source .venv/bin/activate && \
  PROFILE=balanced \
  SYSTEMS=all \
  OUT=runs/m4w13_50_balanced \
  bash deploy/run_colab_m4w13_50_cache.sh
```

The runner writes:

- `runs/m4w13_50_balanced/{b1,b2,b3,b4,controller}/answers.jsonl`
- `predictions.jsonl`, `judgments.jsonl`, `judge_cache.jsonl`, `report.json`, `results.md`
- controller/B4/B3 traces and action logs where applicable
- `runs/m4w13_50_balanced/summary.json`, `summary.md`, `manifest.json`, `_logs/*`
- `/content/m4w13_50_balanced_results.zip`

The run is resumable. Re-run the same command with the same `OUT`; complete
systems are skipped and incomplete systems continue from JSONL progress.

## Controller-Only First Pass

```python
!source .venv/bin/activate && \
  PROFILE=balanced \
  SYSTEMS=controller \
  OUT=runs/m4w13_50_controller_balanced \
  bash deploy/run_colab_m4w13_50_cache.sh
```

## Accuracy-First Alternative

On A100, this runs all systems serially with the 7B quality preset:

```python
!source .venv/bin/activate && \
  PROFILE=quality \
  SYSTEMS=all \
  OUT=runs/m4w13_50_quality \
  bash deploy/run_colab_m4w13_50_cache.sh
```

On A10G, use the quality preset for controller-only:

```python
!source .venv/bin/activate && \
  REQUIRE_A100=0 \
  PROFILE=quality \
  SYSTEMS=controller \
  OUT=runs/m4w13_50_controller_quality \
  bash deploy/run_colab_m4w13_50_cache.sh
```

## Verify Existing Output Without Re-running

```python
!source .venv/bin/activate && python scripts/summarize_m4w13.py runs/m4w13_50_balanced \
  --json-out runs/m4w13_50_balanced/summary.json \
  --md-out runs/m4w13_50_balanced/summary.md \
  --require-complete
!ls -lh /content/*m4w13_50*results.zip runs/m4w13_50_balanced/summary.*
```

## Do Not Use The Old Ollama Notebook Path For This Job

The old notebook cells have three avoidable failure modes:

- `!cd ...` does not persist across cells.
- `ksa_controllerdeploy/colab_requirements.txt` is a path typo.
- `--session-workers 16` with Ollama can overload one daemon and makes failure
  recovery harder than the HF runner's per-system fingerprint/resume/zip path.

## If You Continue The Ollama Thesis Run

Audit note: B1/B2/B3 were accepted on 2026-06-02 for
`runs/m4w13_50_llama/` (`b1` 18.0%, `b2` 38.0%, `b3` 22.0%). Do not rerun
those three baselines for that protocol unless the protocol changes. Continue
with `--systems b4,controller` after restoring the accepted `b1`, `b2`, and
`b3` directories into the same output root.

Use fewer session workers first; four parallel shards can overload one Ollama
daemon when `llama3:8b` is shared by answerer, extractor, and classifier.

```python
!source .venv/bin/activate && python scripts/run_m4w13_ollama.py \
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

The Ollama runner writes per-shard logs under each selected system directory,
for example `runs/m4w13_50_llama/controller/_logs/controller_shard*.log`. If a
shard crashes, it prints the tail of that shard log and stops the other shards
instead of waiting silently. Re-run the same command; `--resume` is enabled by
default and completed `answers.jsonl`/`judgments.jsonl` rows are reused.
