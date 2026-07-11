# M4W13 A10G prompt-slim run — analysis (2026-06-11)

Run: `runs/m4w13_failed_a10g_prompt_slim/controller` — controller on the 7
runs(4) failures, `--k 6 --controller-memory-top-k 20
--controller-retrieval-neighbor-window 0 --no-controller-include-assistant-context`,
`--ollama-num-ctx 32768`. **Merged: 1/7 = 14.3 %.** All facts below are
**[verified]** from the run artifacts.

## The two fixes worked exactly as designed
- **Flags reached the controller** (the bug we fixed): logs show
  `memory_prefilter selected=20/...`, `neighbor_window=0`, `assistant_ctx=False`,
  k=6. Under the old `_apply_t4_quality` these would have been reverted.
- **Budget guard active and logged every sample**; no trim fired because the
  slim flags already kept prompts at **1.2k–4.2k tokens** (vs 11k–53k in runs(4)),
  far under the 32 000 budget.
- **852ce960 is now correct** (`$` → `$400,000`): the one true saturation case,
  cured by giving the model room. **0/7 → 1/7 vs runs(4) on this exact set.**

## The 6 remaining failures are NOT context-budget problems
| session | runs(4) pred | slim pred | gold | bucket | judge note |
|---|---|---|---|---|---|
| 5d3d2817 | senior marketing analyst | **marketing specialist** | Marketing specialist at a small startup | near-miss | gold-token-guard wants `small`,`startup` |
| 4f54b7c9 | 3 | **4** | 5 | counting | exact-token `5` |
| gpt4_59c863d7 | 3 | 3 | five model kits | counting | undercount |
| e493bb7c | above my bed | above my bed | in my bedroom | format | wants room `bedroom` |
| eac54add | Unknown | Unknown | I signed a contract… | abstention | refusal-guard |
| gpt4_45189cb4 | Unknown | Unknown | NBA→CFB→NFL… | abstention | refusal-guard |

Three mechanisms, none fixable by context volume:
1. **Counting / aggregation** (4f54b7c9, gpt4_59c863d7) — model under-enumerates
   distinct items. Slim moved 4f54b7c9 3→4 but still short of 5.
2. **Answer completeness vs a strict lexical gold-token judge** (5d3d2817,
   e493bb7c). 5d3d2817 actually **improved**: dropping assistant-context noise let
   it pick the correct *previous* role ("marketing specialist") instead of the
   current role ("senior marketing analyst"); it only loses on the missing
   "small startup" employer qualifier.
3. **Persistent abstention** (eac54add, gpt4_45189cb4). **Key fact:** both also
   returned `Unknown` in runs(4) at ~21–26k-token prompts. More context did not
   help and less context did not hurt — these are retrieval-targeting / model
   limits, not budget.

## Verdict & recommendation
- **Keep the budget guard — it is the durable win.** Its value is NOT to slim;
  it lets you run *fuller* context *safely* (it would trim a 852ce960-style 63k
  prompt down to ≤32k instead of letting it saturate to 1 token).
- **Do not adopt prompt-slim as the default.** On these hardest cases it cured
  the saturation case and slightly improved two, but it did not address counting,
  format, or abstention, and aggressive slimming risks recall loss elsewhere on
  the full 50.
- **Next real test: full 50 with the validated quality config + the budget guard
  at 32k, no slim flags.** Expectation: reproduce runs(2)'s 35/50 and additionally
  recover saturation cases like 852ce960 (≥36/50) with no regressions — this
  isolates the guard's benefit on the whole set.
- The residual 6 need per-mechanism work, not retrieval tuning: enumeration
  scaffolding / extend the computation-answerer to "how many distinct X" counts;
  fuller answers (emit qualifiers) or a less strict gold-token guard for the
  near-misses; targeted retrieval for the two temporal abstentions.

## Suggested commands
Full-50 guarded (no slim) — the recommended next run:
```bash
SLICE=data/slices/longmemeval_s_cleaned_50_seed0.jsonl \
OUT=runs/m4w13_50_a10g_guarded PROFILE=a10g QUALITY=a10g SYSTEMS=controller \
SESSION_WORKERS=2 OLLAMA_NUM_PARALLEL=2 OLLAMA_MAX_LOADED_MODELS=3 EMBEDDER_DEVICE=cuda \
bash deploy/run_colab_m4w13_a10g_ollama.sh --ollama-num-ctx 32768
```
(Optional A/B on the 7 to test recall, not slim: same but `--k 12
--controller-memory-top-k 32 --controller-retrieval-neighbor-window 1` with
assistant context left ON — the guard keeps it safe.)
