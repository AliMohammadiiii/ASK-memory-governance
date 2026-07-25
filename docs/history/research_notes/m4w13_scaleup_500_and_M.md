# M4-W13 scale-up: full 500-question LongMemEval-S and LongMemEval-M

This is the runbook for taking the M4-W13 evaluation harness from the 50-question
dev slice to the full **500-question** LongMemEval-S set and the larger
**LongMemEval-M** release, with the correctness fixes recommended by the
benchmark analysis (`Memory_Systems_Benchmark_Analysis`).

The harness in scope is the eval triple: the runner
(`scripts/run_m4w13_ollama.py` → `scripts/run_baseline.py`), the loader
(`src/ask/data/longmemeval.py`), and the grader (`src/ask/eval/longmemeval.py`).

## 0. What changed (and why it matters at 500-Q / M)

See `CHANGELOG_scaleup_500_M.md` for the full list. The load-bearing items:

- **Numeric/currency normalization in the grader.** `$1300` is no longer
  false-rejected against gold `$1,300` (the docx §8 false negative). Removes a
  whole class of format-only judge errors that scale with the answerable count.
- **Degenerate-answer detection + retry.** A bare `$` (session 852ce960's
  truncation artifact) now (a) triggers the controller answer-retry and (b) is
  counted and surfaced by the run, instead of silently scoring as a wrong
  reasoning answer. The run fails loudly unless `--allow-blank-answers`.
- **Answerable-only / abstention decomposition** is written into every
  `report.json` (`answerable_accuracy`, `abstention_accuracy`, `n_degenerate_answers`),
  so the abstention artifact (docx §7.1) is visible without re-deriving it.
- **Loader: exact full-set slicing, JSON-array streaming, competency
  canonicalization.** `--n all` returns all 500 deterministically; the large M
  array streams via `ijson`; one odd label can't abort a 500/M load.
- **Runner: correct S-vs-M manifest provenance** via `--dataset`.

## 1. Get the data

```bash
# LongMemEval-S (default)
python deploy/download_longmemeval_s.py --dataset s
# LongMemEval-M (larger; confirm the upstream filename on the HF repo)
python deploy/download_longmemeval_s.py --dataset m
```

The cleaned releases live at the HF dataset `xiaowu0162/longmemeval-cleaned`.
They are JSON arrays. The M array is large — do **not** `json.load` it by hand;
the loader streams it with `ijson` (`pip install ijson`) and `build_slice.py`
converts it to streaming JSONL once.

## 2. Build the full 500-question slice

```bash
# Full LongMemEval-S, no sampling, byte-stable id order:
python scripts/build_slice.py \
  --in  /content/longmemeval/longmemeval_s_cleaned.json \
  --out data/slices/longmemeval_s_full.jsonl --n all

# Full LongMemEval-M (streams the big array, writes light JSONL):
python scripts/build_slice.py \
  --in  /content/longmemeval/longmemeval_m_cleaned.json \
  --out data/slices/longmemeval_m_full.jsonl --n all
```

`--n all` (also `--n 0`/`--n full`) bypasses stratified sampling and returns the
entire release. Confirm the printed competency distribution matches the
published one (70 single-session-user, 56 single-session-assistant, 30
single-session-preference, 133 multi-session, 78 knowledge-update, 133
temporal-reasoning).

## 3. Run the full suite

```bash
# Full 500-Q LongMemEval-S, final (thesis) profile, all five systems:
bash deploy/run_colab_lme_full.sh s thesis all

# Full LongMemEval-M:
bash deploy/run_colab_lme_full.sh m thesis all
```

Notes:
- `--model-profile thesis` is the only profile that can earn the
  `final-candidate` tier on a full, non-synthetic run (the T4 profile in the dev
  run is tagged `development_..._NOT_for_final`).
- Memory systems retrieve top-k, so the answer prompt is bounded by `k`, not by
  the haystack — the 8k context is fine for **M** too. M's extra cost is
  ingestion (embedding ~500 sessions/question); keep the extraction prefilter on
  (the runner's `--controller-memory-top-k`/`--recency-memory-top-k` defaults of
  32) and use `SESSION_WORKERS>1` with `OLLAMA_NUM_PARALLEL` for throughput.
- Resume is on by default; a crashed M run continues from
  `answers.jsonl`/`judgments.jsonl` without re-charging completed questions.

## 4. Seeds and confidence intervals (read before quoting "± N points")

The answerers run at **temperature 0 (greedy)**. Re-running the *same* full slice
with a different `--seed` therefore produces *identical* answers — it does **not**
sample new variance. Two honest options:

1. **Point estimate + bootstrap CI (recommended for the full set).** Run the full
   500 once per system; quote `overall_accuracy` with its bootstrap CI
   (`overall_ci_low/high`). At n=500 the CI is ~±4 points, vs ±10–12 at n=50.
2. **Sampling variance across stratified subsamples.** If you want a
   seed-to-seed spread, build several stratified subsamples and run each:
   ```bash
   for s in 0 1 2; do
     python scripts/build_slice.py --in <cleaned.json> \
       --out data/slices/longmemeval_s_200_seed${s}.jsonl --n 200 --seed ${s}
     bash deploy/run_colab_lme_full.sh s thesis all   # SLICE=... SEED=${s}
   done
   ```
   (Override `SLICE`/`OUT`/`SEED` env vars per draw.) Report mean ± SD across draws.

Do not script "3 seeds on the identical full set" and present it as variance — at
temperature 0 the three runs are the same numbers.

## 5. Verify the run

```bash
# Independent recompute of report.json from raw judgments (same check the docx used):
python scripts/m4w13_validation.py --run-dir runs/lme_s_full_thesis_seed0   # if present
# Or eyeball the new fields:
python - <<'PY'
import json, glob
for f in glob.glob("runs/lme_s_full_thesis_seed0/*/report.json"):
    d=json.load(open(f))
    print(f, "overall=%.3f answerable=%.3f (n=%d) abstain=%.3f (n=%d) degenerate=%d"
          % (d["overall_accuracy"], d["answerable_accuracy"], d["answerable_n"],
             d["abstention_accuracy"], d["abstention_n"], d["n_degenerate_answers"]))
PY
```

A nonzero `n_degenerate_answers` means some answers were truncated bare symbols
(context saturation) — raise `--ollama-num-ctx` or lower `--k` and re-run those,
rather than reporting them as reasoning errors.
