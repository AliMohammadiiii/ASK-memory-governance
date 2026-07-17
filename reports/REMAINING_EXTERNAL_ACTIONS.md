# Remaining external actions

## 1. Rotate the exposed credential

Revoke/rotate the OpenRouter key that was pasted into the task. It returned HTTP
403 before inference and is not stored in the repository or release. Use a new,
authorized key only as a shell environment variable.

## 2. Run the homogeneous LongMemEval final-1.1 experiment

Prerequisites: a newly authorized key, the upstream LongMemEval-M full JSONL,
and the cleaned source JSON. Neither dataset is redistributed.

```bash
cd ksa-memory-governance
export OPENROUTER_API_KEY='<newly-rotated-key>'
export LONGMEMEVAL_DATA='/absolute/path/to/longmemeval_m_full.jsonl'
export LONGMEMEVAL_SRC='/absolute/path/to/longmemeval_m_cleaned.json'

# Two-item API sanity check first.
bash scripts/evaluation/run_longmemeval_final.sh --smoke

# Frozen 180-item × five-system run.
bash scripts/evaluation/run_longmemeval_final.sh --full

# If interrupted, continue without rewriting scored items.
bash scripts/evaluation/run_longmemeval_final.sh --resume
```

The wrapper pins Qwen 3.5 9B for answer/extraction/relation roles, Gemma 4 31B
free as primary judge with the paid route only as operational fallback, MiniLM
on CPU, seed 0, and all five systems on the same 180-item slice.

After completion:

```bash
python3 scripts/verify_homogeneous_run.py \
  --run-root runs_local/lme_final_5systems_180 \
  --slice runs_local/_inputs/longmemeval_m_strat30_seed0.jsonl \
  --sample-from 0 --sample-to 179 \
  --systems controller,b4,b3,b2,b1 --expected-n 180 \
  --expected-answer-model qwen/qwen3.5-9b \
  --expected-answer-provider venice \
  --expected-judge-primary google/gemma-4-31b-it:free \
  --allowed-judge-fallback google/gemma-4-31b-it

bash scripts/evaluation/run_judge_audit.sh runs_local/lme_final_5systems_180
bash scripts/release/package_run_for_review.sh \
  runs_local/lme_final_5systems_180 \
  runs_local/lme_final_5systems_180_review.tar.gz
```

Do not add a LongMemEval headline until the verifier passes and the result ledger
is rebuilt under the frozen claim gate.

## 3. Thesis and defense administration

- Supply the official current University of Tehran thesis template.
- Fill advisor, department, student-number, approval, and examination fields.
- Confirm the institution's required Persian typography and front-matter order.

## 4. Cambridge application

- Confirm the target entry cycle/deadline and Andreas Vlachos's permission and
  supervisory capacity.
- Supply final Master's dates/records, transcript, writing sample, English
  evidence or exemption, referees, and proof for quantitative CV claims.
- Send no email and submit no application until those fields are verified.

## 5. Public release

- Obtain written redistribution consent before adding the two withheld raw human
  annotation CSVs; otherwise keep the current aggregate-only release.
- Create the real public Git remote and follow `GIT_PUSH_GUIDE.md`.
- Select a publication venue, obtain its current official template, and adapt the
  canonical manuscript without changing result-status labels.
