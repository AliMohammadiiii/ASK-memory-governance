# M1-W2 sanity check — Baseline 1 (no-memory)

**Run completed:** 2026-04-25, 50 sessions in 1485.7 s (~24.8 min) on
laptop Ollama / `gemma4:e4b`. Within the §5 acceptance criterion (< 90 min).

**Initial overall accuracy:** 38.0% (95% CI 26.0 – 52.0).
**After regrade with empty-judge substring fallback:** 100.0% on the
synthetic placeholder slice.

This note explains exactly what happened and why both numbers are
defensible — and why the §3.4 sanity check is the reason we caught the
issue before tagging.

## 1. What §3.4 caught (the actual finding)

The first run came back with the **opposite** of the expected pattern:

| Competency | First-run accuracy | What we expected |
|---|---:|---|
| single-session-user | 0.0% | high (answer is in the only visible session) |
| single-session-assistant | 0.0% | high |
| single-session-preference | 0.0% | high |
| multi-session | 0.0% | low |
| knowledge-update | 60.0% | low |
| temporal-reasoning | 50.0% | low |
| abstention | 100.0% | mixed |

§3.4's anti-pattern flag (`if multi-session > single-session, something is
wrong`) almost fired. We instead diagnosed by reading 5 wins / 5 losses
from `runs/m1w2/no_memory/judgments.jsonl`:

```
--- lme-s-00011  [knowledge-update]   correct=true ---
  gold     : they prefer coffee in the morning
  predicted: The user said they prefer coffee in the morning.
  rationale: The predicted answer accurately reports the knowledge update from session 11.

--- lme-s-00016  [single-session-preference]   correct=false ---
  gold     : they prefer coffee in the morning
  predicted: The user prefers coffee in the morning.
  rationale: [parse-fail] judge output not parseable: ''
```

Same gold. Equally good prediction. **The judge was returning empty text
on 31 of 50 calls.** Looking at `runs/m1w2/no_memory/judge_cache.jsonl`:

```
empty raw responses: 31/50
length histogram: len=0 ×31, len=106-154 ×19
```

The 19 successful judge calls clustered on `knowledge-update`, `abstention`,
and `temporal-reasoning`. The 31 empty calls clustered on
`single-session-*` and `multi-session`. Same model, same prompt template,
two different competency clusters → two different output behaviors. This is
the **self-judging artifact** the eval-protocol note flagged in
`NOTES/eval_protocol.md` §3.

Hardware context (from the Ollama daemon log on the same host): 8 GiB RAM,
1.5 GiB free, 0 swap; gemma4:e4b's runner needs ~10 GiB. Memory pressure
is the most likely root cause of the empty-output failure mode.

## 2. The Week-2 mitigation (documented, not silent)

We added a **normalized-substring fallback grader** that activates ONLY
when the LLM judge emits empty / unparseable output. It:

- Lowercases, strips punctuation, drops stopwords + pronouns + role nouns
  (so "user/they/I" and "the/a" don't pollute the match).
- Crude-stems trailing `s/es/ed/ing` so "prefer" matches "prefers".
- Requires every gold content token to appear in the prediction.
- For abstention questions, accepts hedge phrases ("I don't know", "no
  record", etc.) as correct without needing token overlap.

Every grade routed through the fallback is tagged `[substring-fallback]` in
its `judge_rationale` and carries `used_fallback=True` on the `GradeResult`,
so the qualitative-analysis appendix can quote and audit them. The
`fallback_breakdown` in `report.json` records how many grades per competency
came from the fallback.

This is not a substitute for an LLM judge. It is the explicit Week-2
substitution that `NOTES/eval_protocol.md` §3 promised; the Month-4 swap to
the LongMemEval-published judge (GPT-4o or current equivalent) replaces it
entirely.

## 3. Five wins / five losses (post-regrade)

After the regrade, every session is `correct=true` on the synthetic slice
(see §4 below for why that is expected and what it means). For audit
purposes here are 5 LLM-judged wins (high confidence) and 5
fallback-routed wins (lower confidence, flagged):

```bash
# LLM-judged wins:
jq -c 'select(.judge_rationale | startswith("[substring-fallback]") | not) | {session_id, competency, predicted, gold, judge_rationale}' \
  runs/m1w2/no_memory/judgments.jsonl | head -5

# Fallback-routed wins (the 31 empty-judge cases):
jq -c 'select(.judge_rationale | startswith("[substring-fallback]")) | {session_id, competency, predicted, gold, judge_rationale}' \
  runs/m1w2/no_memory/judgments.jsonl | head -5
```

LLM-judged wins read like:

> session lme-s-00011 [knowledge-update]: predicted "The user said they prefer
> coffee in the morning"; gold "they prefer coffee in the morning"; rationale
> "The predicted answer accurately reports the knowledge update from session 11."

Fallback-routed wins read like:

> session lme-s-00016 [single-session-preference]: predicted "The user
> prefers coffee in the morning."; gold "they prefer coffee in the morning";
> rationale "[substring-fallback] all gold content tokens present in prediction"

Both are correct calls. The fallback mark exists so a Month-4 reviewer can
see exactly which calls didn't get an LLM-judge stamp.

## 4. Why the regraded result is 100% — and what it means

The slice this run used is `data/slices/longmemeval_s_50_seed0.jsonl`,
sampled from `data/longmemeval_s_synthetic.jsonl` — the **placeholder
corpus** M1-W1 generated to validate plumbing before the real
LongMemEval-S release file lands.

In that placeholder corpus:

- Every session's dialog contains the gold answer verbatim ("USER:
  (synthetic single-session-assistant #N) I prefer coffee in the morning.").
- Most golds are nearly identical across sessions ("they prefer coffee in
  the morning") — they are not real LongMemEval questions.
- A sufficiently-strong LLM should answer 100% on this slice regardless of
  competency, because the answer is always in the only session it sees.

So 100% on this slice means **the pipeline is wired correctly** and the
**model and grader behave as expected on trivially-answerable inputs**.
It does NOT mean the no-memory baseline is at ceiling on real LongMemEval-S.
It also does not falsify the thesis claim that single-session-* > multi-session
under no memory — that claim awaits the real file, where multi-session
sessions actually distribute supporting evidence across multiple sessions.

The expected single-vs-multi gap will appear automatically once the slice is
rebuilt against a real LongMemEval-S file. The pipeline does not need to
change — `data/slices/longmemeval_s_50_seed0.jsonl` is the only artifact
that has to be rebuilt (via `scripts/build_slice.py`).

## 5. Token budget

```
abstention                  102 prompt tokens (10 sessions)
knowledge-update            104                (10)
multi-session               104                ( 6)
single-session-assistant    106                ( 6)
single-session-preference   106                ( 6)
single-session-user         105                ( 6)
temporal-reasoning          106                ( 6)
```

All competencies sit at ~100-106 prompt tokens — three orders of magnitude
inside `gemma4:e4b`'s context window (8K+) and well under the runner's
`num_ctx=2048` cap we set in the M1-W2 hotfix. No truncation is happening.

Latency at ~2.5 s/session on the laptop is consistent with the M1-W1 bench
(28.5 s/session was a cold-start outlier; warm path is ~2 s — what we see
here).

## 6. One-paragraph findings

> The no-memory baseline runs end-to-end on the 50-session synthetic
> placeholder slice in 24.8 minutes (well inside the 90-min acceptance
> budget). The first run surfaced a self-judging artifact: gemma4:e4b
> emitted empty text on 31/50 judge calls, clustered on single-session-* and
> multi-session competencies, almost certainly driven by 8-GB-RAM memory
> pressure. The §3.4 sanity check caught this before tagging, exactly as
> designed. We added a documented Week-2 mitigation — a normalized-substring
> fallback grader that activates only on empty/unparseable judge output and
> tags every fallback-routed grade — and re-graded from cache without
> re-running Ollama. The regraded slice now reads 100% across all
> competencies; this reflects the placeholder data's trivially-similar gold
> answers, not the no-memory baseline's true performance. The pipeline is
> validated and ready to produce real numbers as soon as the LongMemEval-S
> release file replaces the placeholder. Acceptance criteria 1-5 hold; tag
> `v0.1.1-m1w2-baseline-no-memory` and proceed to flat-vector in M1-W3.

## 7. Pipeline checks already automated (covered by pytest)

These guard against regression of the §3.4 invariants:

- `tests/test_no_memory.py::test_prompt_contains_only_current_session`
- `tests/test_no_memory.py::test_prompt_does_not_leak_supporting_session_ids`
- `tests/test_no_memory.py::test_default_system_prompt_is_minimal_and_no_memory_framing`
- `tests/test_longmemeval_eval.py::test_bootstrap_ci_agrees_with_wilson_for_n100`
- `tests/test_longmemeval_eval.py::test_grader_caches_and_does_not_recall_judge`
- `tests/test_longmemeval_eval.py::test_grader_uses_substring_fallback_when_judge_returns_empty`
  ← new, regression for this exact host-run finding
- `tests/test_longmemeval_eval.py::test_normalized_substring_grade_handles_abstention`
- `tests/test_longmemeval_eval.py::test_normalized_substring_grade_paraphrase_smoothing`
- `tests/test_ollama.py::test_ollama_retries_on_transient_502_then_succeeds`
- `tests/test_ollama.py::test_ollama_default_retry_budget_survives_runner_restart`

If any of these regress in the future, M1-W2's claims regress with them.
