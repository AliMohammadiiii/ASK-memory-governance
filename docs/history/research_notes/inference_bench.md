# Inference benchmark — M1-W1 §3.2

**Run:** Laptop dev (Ollama)
**Backend:** `ollama`
**Model:** `gemma4:e4b`
**GPU/HW:** Apple Silicon / Mac (arm)
**Platform:** macOS-26.3-arm64-arm-64bit (Python 3.12.12)

| Metric | Value |
|--------|-------|
| n_prompts                | 5 |
| prompt_tokens (target)   | 512 |
| max_new_tokens           | 64 |
| **median tokens/sec**    | **2.45** |
| median latency (ms)      | 26172.1 |
| p95 latency (ms)         | 33192.4 |

## Acceptance — laptop dev path (M1-W1 finalization)

This bench documents the **laptop dev path** used to finalize M1-W1 against
a real LLM without GPU access. The original §5.3 acceptance threshold
(≥ 25 tok/s on A100 80GB for a 7B model in bf16) is a separate, GPU-only
criterion that remains pending the GPU runner. The number reported here is
not comparable to that threshold.

What this bench *does* establish:
- the inference harness can drive a real chat-tuned model end-to-end via
  `/api/chat` (`OllamaLLM` chat mode),
- `temperature=0.0 + seed` are honored by the daemon,
- the bench script is operational and produces a structured report.

## Reproduction

```
python scripts/bench_inference.py --ollama --ollama-model gemma4:e4b \
    --n-prompts 5 --prompt-tokens 512 \
    --max-new-tokens 64
```
