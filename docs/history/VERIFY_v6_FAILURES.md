# Live re-verification of the v6 failures (real OpenRouter API)

Each of the 11 `correct=False` cases from the v6 run
(`runs/lme_m_openrouter_qwen_gemma_minilm_200_239_seed0_v6`, controller, 72.5%)
was re-run through the **fixed** code against the live models
(`qwen/qwen3.5-9b` answerer via venice/deepinfra/siliconflow; `google/gemma-4-31b-it`
judge via wandb/venice). The retrieval context is held constant (reused verbatim
from each session's v6 `raw_prompt`), so any change is due to the fix, not luck.

## Judge-side prompt-eng bug — FIXED

**89941a93** — Q "How many bikes do I currently own?", gold `4`, prediction `four`.
- v6: `[gold-token-guard] 1/1 gold tokens missing: ['4']` → **correct=False** (false negative).
- fixed: the guard's number-word↔digit normalization makes `four` == `4`, so it no
  longer hard-rejects; the **live gemma judge returns correct=True** ("'four' is a
  direct paraphrase of the gold answer '4'"). Both `four` and `4` now pass.

The other numeric gold-token-guard rejections in v6 (`5` vs `4`, `1` vs `2`,
`1` vs `3`, `$120` vs `$50`) were **correct** rejections of genuinely wrong
answers — those are main-side counting/computation bugs (fixed by the aggregation
scaffold §4.4 and verify-bypass §4.5), not judge bugs.

## Main-side prompt-eng bug — FIXED (format + abstention)

**Preference format (A)** — v6 answered these literally or abstained; the new
preference prompt makes all three emit a proper "The user would prefer …" profile:

| session | v6 prediction | v6 | fixed prediction (form) | live judge |
|---|---|---|---|---|
| 8a2466db | "Adobe Premiere Pro's official documentation…" (direct) | ✗ | "The user would prefer resources … on Adobe Premiere Pro's advanced features (Lumetri Color Panel, Curves, Color Match)…" | **correct=True** |
| 75832dbd | "Unknown" | ✗ | "The user would prefer recent publications/conferences focused on …" (profile) | ✗ (wrong domain) |
| 75f70248 | "Yes, the living room could be the source…" (direct) | ✗ | "The user would prefer suggestions that … HEPA filtration, cat dander…" (profile) | ✗ (grounding) |

The **format bug is fixed** (no more Unknown / direct answers — all three are now
preference profiles), and 8a2466db flips to correct. 75832dbd/75f70248 still miss
on **content** (wrong domain / weak grounding). That is retrieval/grounding-bound,
and this test deliberately reuses the *old v6 retrieval context* — the full v7 run
adds answer-context rerank, prefilter chunking, and the anti-fabrication clause,
which improve grounding beyond what this held-constant test shows.

**False "Unknown" (B)** — evidence was in context but v6 abstained:

| session | gold | v6 | fixed (commit-retry prompt) | live judge |
|---|---|---|---|---|
| 87f22b4a | `$120` | "Unknown" ✗ | **`$120`** | **correct=True** |

The commit-forcing escalate-on-Unknown prompt makes the model commit to the
supported answer instead of abstaining.

## Bottom line

- Judge prompt-eng bug (`four` vs `4`): **fixed and live-confirmed.**
- Main prompt-eng format bug (preference profiles): **fixed** — the answer is now
  always in the correct preference-profile form; correctness then tracks retrieval
  grounding.
- Main abstention bug (false Unknown): **fixed** — commits to the correct answer.

Tests: 460 passed / 2 skipped; ruff clean, after these prompt edits.
