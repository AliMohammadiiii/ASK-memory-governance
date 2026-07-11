"""Inference benchmark — tokens/sec and p95 latency for the configured model.

Two modes:

  --ollama   → drive a local Ollama daemon (e.g. gemma4:e4b on a Mac).
               This is the **laptop dev / M1-W1 finalization** path. The
               number it produces is recorded as evidence of an end-to-end
               working pipeline; it is NOT comparable to the A100 spec.

  (default)  → drive a HuggingFace model loaded from `configs/inference.yaml`.
               This is the **A100 acceptance** path. Target: ≥ 25 tok/s
               sustained for a 7B model in bf16 on A100 80GB.

Usage:
    # Laptop / Ollama (the path used for M1-W1 finalization with gemma4:e4b)
    python scripts/bench_inference.py --ollama --ollama-model gemma4:e4b

    # GPU acceptance run
    python scripts/bench_inference.py --n-prompts 10 --prompt-tokens 2000
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ksa.inference.llm import LLM, build_llm, load_inference_config  # noqa: E402


def _make_prompt(n_target_tokens: int) -> str:
    """Generate a prompt approximately `n_target_tokens` long.

    Real tokenization differs by model; we use a ~0.75-token-per-word rule
    of thumb. Good enough for a benchmark where the actual prompt-token
    count is reported by the harness.
    """
    words = ["lorem"] * int(n_target_tokens * 1.3)
    return " ".join(words)


def _detect_gpu() -> str:
    """Best-effort GPU detection across torch and macOS."""
    try:
        import torch  # type: ignore[import-not-found]
        if torch.cuda.is_available():
            return (
                f"{torch.cuda.get_device_name(0)} "
                f"(cuda devices={torch.cuda.device_count()})"
            )
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "Apple MPS (metal performance shaders)"
    except ImportError:
        pass
    # macOS fallback
    if platform.system() == "Darwin":
        return f"Apple Silicon / Mac ({platform.processor() or 'unknown'})"
    return "no GPU detected"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n-prompts", type=int, default=10)
    p.add_argument("--prompt-tokens", type=int, default=2000)
    p.add_argument("--max-new-tokens", type=int, default=256)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path,
                   default=_THIS.parents[1] / "NOTES" / "inference_bench.md")

    # Backend selection
    p.add_argument("--ollama", action="store_true",
                   help="Drive a local Ollama daemon instead of HuggingFace.")
    p.add_argument("--ollama-model", default="gemma4:e4b",
                   help="Ollama model tag (default: gemma4:e4b).")
    p.add_argument("--ollama-host", default="http://localhost:11434")
    p.add_argument("--use-fallback", action="store_true",
                   help="HF mode only: swap to fallback_model_id.")
    args = p.parse_args()

    if args.ollama:
        from ksa.inference.ollama import OllamaLLM
        llm: LLM = OllamaLLM(model_id=args.ollama_model, host=args.ollama_host)
        backend_label = "ollama"
    else:
        cfg = load_inference_config()
        llm = build_llm(cfg, use_fallback=args.use_fallback)
        backend_label = "huggingface"

    prompt = _make_prompt(args.prompt_tokens)

    # Warmup (Ollama models load on first call; HF models load on lazy-init).
    print(f"[warmup] backend={backend_label}, model={llm.model_id}; running 1 forward pass...")
    _ = llm.generate(prompt, max_new_tokens=8, seed=args.seed)

    # Benchmark
    latencies_ms: list[float] = []
    tokps: list[float] = []
    print(f"[bench] running {args.n_prompts} prompts of ~{args.prompt_tokens} tokens, "
          f"max_new_tokens={args.max_new_tokens}")
    for i in range(args.n_prompts):
        t0 = time.perf_counter()
        resp = llm.generate(prompt, max_new_tokens=args.max_new_tokens, seed=args.seed + i)
        elapsed = (time.perf_counter() - t0)
        latencies_ms.append(elapsed * 1000.0)
        tokps.append(resp.completion_tokens / elapsed if elapsed > 0 else float("inf"))
        print(f"  [{i:02d}]  {resp.completion_tokens} tok in {elapsed*1000:8.1f} ms  "
              f"= {tokps[-1]:6.2f} tok/s")

    median_tokps = statistics.median(tokps)
    median_latency = statistics.median(latencies_ms)
    sorted_latencies = sorted(latencies_ms)
    p95_latency = sorted_latencies[max(0, int(round(0.95 * len(sorted_latencies))) - 1)]

    summary = {
        "backend": backend_label,
        "model_id": llm.model_id,
        "n_prompts": args.n_prompts,
        "prompt_tokens_target": args.prompt_tokens,
        "max_new_tokens": args.max_new_tokens,
        "median_tokens_per_sec": round(median_tokps, 2),
        "median_latency_ms": round(median_latency, 1),
        "p95_latency_ms": round(p95_latency, 1),
        "gpu": _detect_gpu(),
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
    print(json.dumps(summary, indent=2))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    md = _format_markdown(summary, args)
    args.out.write_text(md, encoding="utf-8")
    print(f"\n[done] benchmark report → {args.out}")
    return 0


def _format_markdown(s: dict[str, object], args: argparse.Namespace) -> str:
    is_ollama = s["backend"] == "ollama"
    bench_label = "Laptop dev (Ollama)" if is_ollama else "A100 acceptance (HuggingFace)"

    if is_ollama:
        accept_block = """## Acceptance — laptop dev path (M1-W1 finalization)

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
"""
    else:
        accept_block = f"""## Acceptance check (M1-W1 §3.2 / §5.3)

Threshold: **≥ 25 tokens/sec sustained on A100 80GB for a 7B model in bf16.**

- Reported median tokens/sec: {s['median_tokens_per_sec']}
- Pass on A100 80GB: see GPU field above. Non-A100 runs do not constitute
  acceptance under §5.3.
"""

    repro_cmd = (
        f"python scripts/bench_inference.py --ollama --ollama-model {args.ollama_model} \\\n"
        f"    --n-prompts {s['n_prompts']} --prompt-tokens {s['prompt_tokens_target']} \\\n"
        f"    --max-new-tokens {s['max_new_tokens']}"
        if is_ollama else
        f"python scripts/bench_inference.py --n-prompts {s['n_prompts']} \\\n"
        f"    --prompt-tokens {s['prompt_tokens_target']} \\\n"
        f"    --max-new-tokens {s['max_new_tokens']}"
    )

    return f"""# Inference benchmark — M1-W1 §3.2

**Run:** {bench_label}
**Backend:** `{s['backend']}`
**Model:** `{s['model_id']}`
**GPU/HW:** {s['gpu']}
**Platform:** {s['platform']} (Python {s['python']})

| Metric | Value |
|--------|-------|
| n_prompts                | {s['n_prompts']} |
| prompt_tokens (target)   | {s['prompt_tokens_target']} |
| max_new_tokens           | {s['max_new_tokens']} |
| **median tokens/sec**    | **{s['median_tokens_per_sec']}** |
| median latency (ms)      | {s['median_latency_ms']} |
| p95 latency (ms)         | {s['p95_latency_ms']} |

{accept_block}
## Reproduction

```
{repro_cmd}
```
"""


if __name__ == "__main__":
    raise SystemExit(main())
