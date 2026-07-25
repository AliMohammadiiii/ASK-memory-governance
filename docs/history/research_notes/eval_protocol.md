# LongMemEval-S grading protocol — M1-W2 (Baseline 1)

**Source:** Wu et al. (2025), *LongMemEval: Benchmarking Chat Assistants on
Long-Term Interactive Memory*, §4 (Evaluation Protocol).
**Scope:** how the no-memory baseline (and every later baseline + the
controller in Month 4) maps a model answer to a boolean correctness grade.
**Decision date:** 2026-04-25, with the Month-4 substitution path explicit.

## 1. What LongMemEval-S grades on (and how)

LongMemEval-S grades open-ended chat-assistant answers with an **LLM-as-judge**
rubric, not exact match or fuzzy string match. The published paper specifies a
single-prompt judge that compares `(question, gold_answer, predicted_answer)`
and emits a boolean. The judge is asked to be *generous* about paraphrase but
*strict* about contradicted or fabricated content; partial-credit is collapsed
to {correct, incorrect}. The paper's recommended judge is GPT-4o (frontier
proprietary) at temperature 0.

We adopt the published rubric verbatim (rubric text reproduced in
`src/ask/eval/longmemeval.py:_JUDGE_PROMPT_TEMPLATE`) but substitute the judge
model — see §3.

There are two domain-specific subtleties the published rubric handles, which
our reimplementation must preserve:

1. **Abstention questions** (`competency = "abstention"`) — the gold answer
   asks the assistant to refuse to answer. A correct prediction is one that
   declines to commit to a fact. The judge is given an abstention-aware prompt
   variant; in our implementation we pass the competency into the judge so the
   prompt can branch.
2. **Knowledge-update questions** — the gold answer is the *new* (post-update)
   value. A prediction that returns the *old* value is incorrect even though
   it appears in the dialog. The judge sees `gold_answer` only (not the old
   value), so this is implicit: the prediction must match the gold, not the
   pre-update fact.

## 2. The grade interface

A grade is `GradeResult(correct: bool, judge_score: float, judge_rationale: str, competency: str)`:

* `correct` is the boolean used in accuracy aggregation.
* `judge_score` is the model's emitted score in `{0.0, 1.0}` (we coerce; the
  rubric is binary). Reserved as `float` for forward-compat with partial-credit
  variants in MGP-6.
* `judge_rationale` is the judge's free-text justification — preserved verbatim
  for the qualitative-analysis appendix in Chapter 4.
* `competency` is carried through so per-competency rollups don't need to
  re-join against the slice.

## 3. Judge model — Week 2 substitution

| Slot | Week 2 (this task) | Month 4 (reviewed result tables) |
|---|---|---|
| Judge model | `gemma4:e4b` via local Ollama | LongMemEval-published judge (GPT-4o or current equivalent) |
| Why | Self-hosted, no API cost, deterministic at `temperature=0` + fixed seed; matches the answerer the dev work targets | Reproducibility against the published benchmark; eliminates self-judging artifacts |

**Self-judging caveat (acknowledged):** in Week 2 the judge and the answerer
are the same model. This biases the grade upward on questions where the model
"agrees with itself" but is wrong, and downward on questions where the model's
own paraphrase differs from the gold. We do **not** treat the Week-2 numbers
as final. They are a development scaffold for §3.4 sanity-checks and a sanity
floor for the Week-3 flat-vector run, not a thesis result. Risk #1 in the
M1-W2 task spec covers the substitution.

The substitution is one config flip in Month 4: pass a different `LLM` instance
to `LongMemEvalGrader`. The evaluator code is judge-model-agnostic.

## 4. Caching

Judge calls are by far the most expensive element of evaluation reruns.

* Cache key: `sha256( prompt_text )` where `prompt_text` is the fully-rendered
  judge prompt (rubric + question + gold + prediction). Same key → same
  judgment, even if upstream order changes.
* Cache file: `runs/<run_dir>/judge_cache.jsonl` — append-only, one
  `{key, response}` JSON object per line. Loaded as a dict on `__init__`.
* The cache is per-judge-model. The judge `model_id` is included in the key.
* **Invalidation:** changing the rubric text (the `_JUDGE_PROMPT_TEMPLATE`
  constant) changes the cache key automatically because the template text is
  part of `prompt_text`. No manual bump needed.

This means a re-run of the evaluator after a code-only change re-loads cached
judgments without re-invoking Ollama, finishing in seconds.

## 5. What we do *not* do (deferred)

* No partial-credit grading — `judge_score` is binary in Week 2.
* No multi-judge ensemble — single-judge in Week 2; ensemble is a Month-4 stretch.
* No human spot-check loop — §3.4 sanity-check covers 5 wins / 5 losses by
  hand, but no formal kappa.
* No abstention F-beta — abstention competency is graded through the same
  binary rubric in Week 2; calibration metrics are deferred to Month 4.

## 6. Exit criterion

This note exists. The judge prompt template is implemented in
`src/ask/eval/longmemeval.py` and exercised in `tests/test_longmemeval_eval.py`
on hand-crafted right/wrong fixtures.
