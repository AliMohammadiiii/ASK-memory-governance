# Remaining external actions

## 1. Keep the credential out of artifacts

Use a valid OpenRouter key only as a shell environment variable. It is not stored
in the repository, run manifest, or release artifacts. Rotate any credential that
has been exposed outside its intended environment.

## 2. Run the homogeneous LongMemEval final experiment

Prerequisites: a valid key, the upstream LongMemEval-M full JSONL,
and the cleaned source JSON. Neither dataset is redistributed.

```bash
cd ask-memory-governance
export OPENROUTER_API_KEY='<your-valid-key>'
export LONGMEMEVAL_DATA='/absolute/path/to/longmemeval_m_full.jsonl'
export LONGMEMEVAL_SRC='/absolute/path/to/longmemeval_m_cleaned.json'

# Two-item API sanity check first.
bash scripts/evaluation/run_longmemeval_final.sh --smoke

# Frozen 180-item × five-system run.
bash scripts/evaluation/run_longmemeval_final.sh --full

# If interrupted, continue without rewriting scored items.
bash scripts/evaluation/run_longmemeval_final.sh --resume
```

The wrapper pins Qwen 3.5 9B for extraction, relation, final answers, and
answer-contract retries. The paid Gemma 4 31B route is the only judge; model
fallback is disabled. MiniLM runs on CPU with seed 0.
After a full run, the wrapper also checks the controller's pre-specified 85%
target (at least 153/180) and exits non-zero if it is not reached.

After completion:

```bash
python3 scripts/verify_homogeneous_run.py \
  --run-root runs_local/lme_final_5systems_v12_qwen_180 \
  --slice runs_local/_inputs/longmemeval_m_strat30_seed0.jsonl \
  --sample-from 0 --sample-to 179 \
  --systems controller,b4,b3,b2,b1 --expected-n 180 \
  --expected-answer-model qwen/qwen3.5-9b \
  --allowed-auxiliary-model qwen/qwen3.5-9b \
  --expected-judge-primary google/gemma-4-31b-it

bash scripts/evaluation/run_judge_audit.sh runs_local/lme_final_5systems_v12_qwen_180
bash scripts/release/package_run_for_review.sh \
  runs_local/lme_final_5systems_v12_qwen_180 \
  runs_local/lme_final_5systems_v12_qwen_180_review.tar.gz
```

Share `final_summary.json`, `controller_accuracy_gate.json`, and `manifest.json`
when diagnosing a controller-only final run.

Do not add a LongMemEval headline until the homogeneity verifier and controller
accuracy gate pass and the result ledger is rebuilt under the frozen claim gate.

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
