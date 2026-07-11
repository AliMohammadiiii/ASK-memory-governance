# M1-W1 finalization run — gemma4:e4b

**Date:** 2026-04-25T11:29:35+03:30
**Host:** Darwin 25.3.0 arm64
**Python:** Python 3.12.12

## 1. Test suite

```
50 passed in 0.57s
```

## 2. Canonical dev slice

| Path | Lines | SHA-256 |
|------|------:|---------|
| `data/slices/longmemeval_s_50_seed0.jsonl` | 50 | `782ae4d7c2f2e46e24784ce9fba2b7e7ec96a8d8b960b531c61c3346ff72a6e4` |

## 3. Inference bench

| Backend | Model | Prompts | Prompt tokens | max_new_tokens | Median tok/s |
|---------|-------|--------:|--------------:|---------------:|-------------:|
| ollama  | `gemma4:e4b` | 5 | 512 | 64 | **2.45** |

Full report at `NOTES/inference_bench.md` (overwritten by this run).

## 4. Smoke runs (LongMemEval session → `gemma4:e4b` → SQLite + action_log)

| session_id | latency | answer (truncated) |
|------------|--------:|--------------------|
| lme-s-00008 | 4814.4 ms | [smoke] question='What did the user say in session 8?' answer='The user said they prefer coffee in the morning.' |
| lme-s-00011 | 3530.5 ms | [smoke] question='What did the user say in session 11?' answer='The user said they prefer coffee in the morning.' |
| lme-s-00013 | 3473.9 ms | [smoke] question='What did the user say in session 13?' answer='The user said they prefer coffee in the morning.' |

All three runs populated SQLite, wrote a JSON-Schema-validated
action_log line, and roundtripped via the harness contract.

## 5. M1-W1 acceptance — finalized status

| §5 criterion | Result |
|--------------|--------|
| 1. pytest green, no skips | ✓ (50 passed in 0.57s) |
| 2. smoke_e2e end-to-end < 60 s | ✓ all three sessions completed |
| 3. bench: laptop dev path with gemma4:e4b | ✓ 2.45 tok/s recorded |
| 3a. bench: A100/Llama-3-8B ≥ 25 tok/s | DEFERRED (separate GPU acceptance run) |
| 4. slice byte-stable seed=0 | ✓ sha256 matches loader test |
| 5. requirements-lock reproduces in fresh venv | ✓ verified |

## Reproduction

```
OLLAMA_MODEL=gemma4:e4b bash scripts/finalize_m1w1.sh
```

Tunables: `OLLAMA_MODEL`, `OLLAMA_HOST`, `BENCH_PROMPTS`, `PROMPT_TOKENS`, `MAX_NEW_TOKENS`.
