# Running the M1-W1 smoke pipeline on your machine

The model used to **finalize M1-W1** is `gemma4:e4b` via your local Ollama
daemon. The original §5.3 A100/Llama-3-8B threshold remains a separate
GPU-acceptance step — see `NOTES/inference_bench.md` and `NOTES/finalize_m1w1.md`.

## TL;DR — finalize Week 1 in one command

Run on your Mac:

```
cd ~/Documents/Master/ask_controller
ollama serve &
ollama pull gemma4:e4b
bash scripts/finalize_m1w1.sh
```

That script runs pytest, records the slice digest, runs the inference
bench against `gemma4:e4b`, runs `smoke_e2e.py` on three sessions, and
writes `NOTES/finalize_m1w1.md` summarizing all of it.

Tunables (env vars):

```
OLLAMA_MODEL=gemma4:e4b      # model tag
OLLAMA_HOST=http://localhost:11434
BENCH_PROMPTS=5              # bench iterations (laptop is slow; keep low)
PROMPT_TOKENS=512            # rough prompt size for bench
MAX_NEW_TOKENS=64            # generation cap for bench
```

## Three dev paths (least → most expensive)

### Path A — fully hermetic (FakeLLM, no network)

Verified inside the sandbox. 0.27 s end-to-end.

```
PYTHONPATH=src python3 scripts/smoke_e2e.py \
    --slice data/slices/longmemeval_s_50_seed0.jsonl \
    --session-id lme-s-00008 \
    --db /tmp/smoke.sqlite \
    --fake
```

### Path B — real model via your local Ollama (`gemma4:e4b`)

The path used for **M1-W1 finalization**. Verified working on your Mac
(28.5 s wall-clock, 11 completion tokens, clean one-sentence answer).

```
PYTHONPATH=src python3 scripts/smoke_e2e.py \
    --slice data/slices/longmemeval_s_50_seed0.jsonl \
    --session-id lme-s-00008 \
    --db /tmp/smoke.sqlite \
    --ollama --ollama-model gemma4:e4b
```

Or via the local config preset (so you don't have to retype flags):

```
INFERENCE_CONFIG=configs/inference-local.yaml \
PYTHONPATH=src python3 scripts/smoke_e2e.py \
    --slice data/slices/longmemeval_s_50_seed0.jsonl \
    --session-id lme-s-00008 \
    --db /tmp/smoke.sqlite
```

### Path C — A100 / Llama-3-8B (GPU acceptance run)

Separate criterion. Pending GPU queue.

```
python3 scripts/bench_inference.py \
    --n-prompts 10 --prompt-tokens 2000 --max-new-tokens 256
```

## What about the dev slice?

`data/slices/longmemeval_s_50_seed0.jsonl` is currently built from a
**synthetic** placeholder corpus at `data/longmemeval_s_synthetic.jsonl`
(200 sessions, deterministic, generated inside the sandbox to enable
smoke testing). When you receive LongMemEval-S, swap in the real file
and re-run:

```
python3 scripts/build_slice.py \
    --in  data/longmemeval_s.jsonl \
    --out data/slices/longmemeval_s_50_seed0.jsonl \
    --n 50 --seed 0
```

The slicer is byte-stable under fixed seed (verified by
`tests/test_longmemeval.py::test_slice_jsonl_is_byte_stable`).

## Optional: pydantic-ai for structured extraction

The harness ships an optional wrapper at
`src/ask/inference/structured_pai.py`. Install:

```
pip install pydantic-ai pydantic-ai-slim[ollama]
```

Then:

```
from ask.inference.structured_pai import structured_via_pydantic_ai
from pydantic import BaseModel

class Extraction(BaseModel):
    text: str
    confidence: float

obj = structured_via_pydantic_ai(
    model="ollama:gemma4:e4b",
    prompt="Extract the user's preference: 'I love tea.'",
    schema=Extraction,
)
```

The hand-rolled `StructuredLLM` in `src/ask/inference/llm.py` continues
to be the M1-W1 default — it's the path under test. pydantic-ai is a
drop-in alternative for Month 2 when the relation classifier ships and
we want grammar-constrained generation.

## Why `/api/chat` and not `/api/generate`?

Chat-tuned models (Gemma, Llama-Instruct, Qwen-Instruct) need their chat
template applied to produce real answers. `/api/chat` does this
automatically; `/api/generate` does not, which is why the first dev run
returned `answer=''` (the model burned its 128-token budget on whitespace
and special tokens). `OllamaLLM(chat=True)` is the default, applied via
`scripts/smoke_e2e.py --ollama`.
