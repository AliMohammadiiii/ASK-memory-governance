# M4-W13 T4 Controller Partial Answer Analysis

Source upload: `/Users/ali/Downloads/runs(1).zip`
Imported source root: `/Users/ali/Documents/Master/_incoming_runs1/content/ask_controller_mgp6_t4_colab/runs/m4w13_50_t4_ollama/controller`
Run status: partial, controller-only, `11/50` completed.
Manifest: `complete=false`, `model_profile=t4`, `run_tier=development`, `raw_turn_fallback=false`, `controller_include_assistant_context=false`.

## Executive Verdict

This is not a final LongMemEval-S artifact. It is a useful partial diagnostic
for the controller path. The controller completed 11 examples and got 5 correct
for `45.5%` partial accuracy.

The dominant failure mode is not answer generation. It is memory retrieval /
coverage before answer generation:

- `Unknown` was emitted for `8/11` answers.
- All incorrect refusals were judged by the refusal guard.
- `Supersede` never fired in these 11 examples: action log totals are
  `Keep=330`, `Abstain=19`, `Supersede=0`.
- Relation routing was mostly non-updating: `unclear=281`, `support=15`,
  `contradict=1`.

The current LongMemEval-S controller path is behaving mostly like a
precision-biased filtered retriever with abstention, not like an active revision
controller.

## Aggregate Numbers

| Metric | Value |
|---|---:|
| Completed examples | 11 / 50 |
| Correct | 5 / 11 |
| Partial accuracy | 45.5% |
| Unknown answers | 8 / 11 |
| Mean latency | 284.9 s/example |
| Median latency | 234.1 s/example |
| Total recorded latency | 52.2 min |

By competency:

| Competency | Correct / n |
|---|---:|
| multi-session | 1 / 4 |
| knowledge-update | 3 / 4 |
| single-session-user | 1 / 1 |
| single-session-assistant | 0 / 2 |

## Per-Answer Analysis

| # | Session | Competency | Prediction | Gold | Result | Root cause |
|---:|---|---|---|---|---|---|
| 1 | `078150f1` | multi-session | `$50` | `$50` | correct | Retrieved both supporting sessions and computed `250 - 200`. This is a clean success. |
| 2 | `08e075c7` | knowledge-update | `6 months` | `9 months` | wrong | Stale-memory failure. Retrieval hit only `answer_cdbe2250_1` with the old `6 months` fact and missed `answer_cdbe2250_2`, the update. No `Supersede` action fired. |
| 3 | `0ddfec37_abs` | knowledge-update abstention | `Unknown` | insufficient information: baseball, not football | correct | Abstention was appropriate. Retrieved baseball/vinyl facts, no football evidence. |
| 4 | `10d9b85a` | multi-session | `Unknown` | `3 days` | wrong | Retrieval miss. Neither support session `answer_e0585cb5_1/2` was retrieved; top-5 memories were unrelated meditation/visits/meal-planning items. |
| 5 | `15745da0` | single-session-user | `three months now` | `three months` | correct | Exact supporting memory was top-1. Good simple fact retrieval. |
| 6 | `1903aded` | single-session-assistant | `Unknown` | `Transcriptionist.` | wrong | Assistant-context gap. Support session was retrieved, but only the user topic `"work from home jobs for seniors"` was available; the answer lived in assistant text. `controller_include_assistant_context=false`. |
| 7 | `2133c1b5_abs` | knowledge-update abstention | `Unknown` | insufficient information: Harajuku, not Shinjuku | correct | Abstention was appropriate. Retrieved Harajuku evidence and no Shinjuku evidence. |
| 8 | `21d02d0d` | multi-session | `Unknown` | `2` | wrong | Partial support hit but missing decisive evidence. Support sessions were retrieved, but top chunks contained general running/training facts, not the missed-run count. |
| 9 | `2698e78f_abs` | knowledge-update abstention | `Unknown` | insufficient information: Dr. Smith, not Dr. Johnson | correct | Correct abstention, but weak evidence path: no support sessions were retrieved. The answer is correct because retrieved context was irrelevant, not because the system demonstrated the Smith/Johnson distinction. |
| 10 | `352ab8bd` | single-session-assistant | `Unknown` | `20%` HAMT framerate improvement | wrong | Assistant-context / retrieval miss. The support session was absent from top-5; retrieved items were unrelated DQN/farming/car facts. |
| 11 | `3fe836c9` | multi-session | `Unknown` | `$25,000` | wrong | Support sessions were retrieved but the decisive final-sale-price fact was missing from the retrieved chunks. The prompt had pre-approval `$350,000`, but not the sale price needed to compute the difference. |

## Retrieval Diagnosis

Support-session behavior:

| Category | Count | Sessions |
|---|---:|---|
| Correct with support hit | 4 | `078150f1`, `0ddfec37_abs`, `15745da0`, `2133c1b5_abs` |
| Correct without support hit | 1 | `2698e78f_abs` |
| Wrong with support hit but insufficient/wrong chunks | 4 | `08e075c7`, `1903aded`, `21d02d0d`, `3fe836c9` |
| Wrong with no support hit | 2 | `10d9b85a`, `352ab8bd` |

Interpretation:

1. The retriever often finds the right session family but not the decisive turn.
2. Single-session-assistant examples are structurally disadvantaged because
   assistant context is disabled.
3. Knowledge-update can still retrieve stale facts because the controller path
   is not producing `Supersede` actions in LongMemEval-S.
4. Correct abstentions are partly encouraging, but at least one correct
   abstention (`2698e78f_abs`) comes from irrelevant retrieval rather than a
   controlled contradiction/absence judgment.

## Controller Decision Behavior

Across the 11 completed examples:

| Action | Count |
|---|---:|
| Keep | 330 |
| Abstain | 19 |
| Supersede | 0 |

Relation trace:

| Routed relation | Count |
|---|---:|
| unclear | 281 |
| support | 15 |
| contradict | 1 |

This explains the stale-update failure on `08e075c7`: even when old and new
facts coexist in the broader support set, the open-corpus prior matching and
relation routing are not producing revision actions.

## What This Means For The Thesis

This partial run supports three claims:

1. The answerer can use retrieved memory when the exact evidence reaches the
   prompt (`078150f1`, `15745da0`).
2. The current LongMemEval-S controller path still has a coverage bottleneck:
   missing support chunks cause `Unknown` on answerable questions.
3. LongMemEval-S is not yet demonstrating the K/S/A revision mechanism because
   `Supersede=0` in this partial run.

It does not support any final all-system LongMemEval-S claim yet.

## Recommended Next Run

Resume the controller run to 50 examples first:

```bash
python scripts/run_m4w13_ollama.py \
  --model-profile t4 \
  --slice data/slices/longmemeval_s_cleaned_50_seed0.jsonl \
  --out runs/m4w13_50_t4_ollama \
  --systems controller \
  --seed 0 \
  --n-bootstrap 1000 \
  --ollama-host http://127.0.0.1:11434 \
  --ollama-timeout-s 1800 \
  --judge-timeout-s 1800 \
  --embedder-backend sentence_transformer \
  --embedder-device cuda
```

For a follow-up diagnostic run after this finishes, enable assistant context:

```bash
python scripts/run_m4w13_ollama.py \
  --model-profile t4 \
  --slice data/slices/longmemeval_s_cleaned_50_seed0.jsonl \
  --out runs/m4w13_50_t4_controller_assistant_ctx \
  --systems controller \
  --seed 0 \
  --n-bootstrap 1000 \
  --ollama-host http://127.0.0.1:11434 \
  --ollama-timeout-s 1800 \
  --judge-timeout-s 1800 \
  --embedder-backend sentence_transformer \
  --embedder-device cuda \
  --controller-include-assistant-context
```

That diagnostic directly targets the two single-session-assistant failures and
some missing-evidence cases.

