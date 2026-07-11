# Standard: role-based models + 4B→9B cascade, served by vLLM

This is the project's standard execution architecture for the LLM pipeline. It
replaces "run everything with one big model in-process".

## Principle

Do not run every role with 9B, and do not load models inside each Python
process. Assign models by role, serve them with vLLM (continuous batching), and
spend the big model only where it changes the Keep/Supersede/Abstain decision.

| Pipeline stage              | Model            | Why |
|-----------------------------|------------------|-----|
| extraction                  | **4B** (fast)    | short structured JSON, parallel-friendly |
| postprocessor               | deterministic    | no model |
| relation classification     | **4B → 9B cascade** | escalate decision-critical/ambiguous items |
| controller scoring          | deterministic    | no model |
| generation / dev QA         | 4B (dev) / 9B    | dev = 4B; quality = 9B |
| final-candidate / judge      | **9B** (or external) | 4B is risky for final evidence |
| ambiguous cases             | route to **9B**  | small accuracy loss, big speedup |

Quant: BF16 official HF weights on the A100 40GB (9B BF16 ≈ 19GB, fits with KV
for 8K). GGUF only for portability. vLLM is the server (PagedAttention,
continuous batching, prefix caching, OpenAI-compatible API).

## Cascade escalation rule (implemented in ControllerOrchestrator)

The fast (4B) relation classifier runs first; the item is re-classified by the
9B classifier when ANY of these hold (`_should_escalate`):

```
escalate =
    relation_to_prior_state in {contradict, supersede, unclear}   # decision-critical/ambiguous
 or extraction_confidence < 0.75                                  # feature c
 or marker_burden > 0.35                                          # feature rho (negation/hedge)
```

This maps to the controller's own features (c, r, rho). `relation_score` from
the literal proposal is not exposed by the label-only two-stage classifier, so
the decision-critical relation set carries that intent instead. The relation
cache records `model_used` per item, and each question's metadata carries
`relation_escalations`, `relation_escalation_eligible`,
`relation_model_id`, `relation_escalation_model_id` — so the escalation rate is
auditable per run.

Flags (run_baseline.py): `--classifier-escalation-openai-model`,
`--classifier-escalation-openai-base-url` (or `--classifier-escalation-hf-model`),
`--escalation-extraction-confidence`, `--escalation-marker-burden`,
`--escalation-relations`. The cascade is OFF unless an escalation model is set
(backward compatible).

## Non-thinking (Qwen3.5)

Server-side: `vllm serve ... --default-chat-template-kwargs '{"enable_thinking": false}'`.
Per-request the backend also sends `chat_template_kwargs={"enable_thinking": false}`
(`--no-openai-enable-thinking`), and `OpenAICompatibleLLM` strips any stray
`<think>…</think>` defensively. For extraction/relation, set `guided_json` (the
backend forwards it to vLLM guided decoding) or rely on `response_format:
json_object` + the StructuredLLM repair.

## Execution model: concurrency without rewriting the controller

The controller is sequential *within* a session (Supersede/Abstain order
matters), but the 500 sessions are independent. Because vLLM holds the weights,
the Python side is a thin HTTP client: we run many lightweight **session-shard
client processes** (`run_baseline --num-shards N --shard-index k`), all hitting
vLLM at once. vLLM continuously batches their concurrent requests on the GPU.
Concurrency ≈ shards. `scripts/run_vllm_cascade.py` fans out the shards and
merges them.

VRAM budget on the 40GB card: the two vLLM servers own the GPU (e.g. 4B
GPU_FRAC≈0.45 + 9B≈0.50 ≈ 33–34GB). The retriever therefore runs on **CPU**
(`--embedder-device cpu`, the driver default) — loading the jina embedder on the
GPU inside every shard process exhausts VRAM (OOM). CPU embedding is fine on the
64-core/128GB host and keeps shards GPU-free, so `--shards` scales freely.

Phased run (fairest benchmark, one server at a time at GPU_FRAC≈0.90):
```
Phase 1: 4B server up   → extraction + primary relation for all systems
Phase 2: 9B server up   → escalation + answerer + judge
```
Or both servers co-resident on the 40GB card (4B GPU_FRAC≈0.45, 9B≈0.50).

## Commands

Serve (two tmux windows):
```bash
MODEL=./models/qwen35-4b NAME=qwen35-4b PORT=8000 MAX_NUM_SEQS=128 GPU_FRAC=0.45 bash deploy/serve_vllm.sh
MODEL=./models/qwen35-9b NAME=qwen35-9b PORT=8001 MAX_NUM_SEQS=64  GPU_FRAC=0.50 bash deploy/serve_vllm.sh
```

Run the suite with cascade + role routing + high concurrency:
```bash
OPENAI_API_KEY=EMPTY python scripts/run_vllm_cascade.py \
  --slice data/slices/longmemeval_m_full.jsonl \
  --out runs/lme_m_full_vllm_cascade_seed0 \
  --systems b1,b2,b3,b4,controller --shards 32 \
  --fast-base-url http://localhost:8000/v1 --fast-model qwen35-4b \
  --big-base-url  http://localhost:8001/v1 --big-model  qwen35-9b
```
(`OPENAI_API_KEY=EMPTY` because the backend requires a key string; vLLM ignores
its value. Set `--shards` to roughly the server's `--max-num-seqs`.)

## Suggested vLLM knobs (A100 40GB, short extraction/relation prompts)

| model   | --max-num-seqs | --max-num-batched-tokens | client shards |
|---------|----------------|--------------------------|---------------|
| 4B BF16 | 128–256        | 65536–98304              | 128–256       |
| 9B BF16 | 64–128         | 32768–65536              | 64–128        |

## Reproducibility logging

Every run must log: model_name (per role), dtype, max_model_len, max_num_seqs,
temperature, seed, and the cascade escalation rate. The per-question metadata
already records the relation/escalation model ids and escalation counts;
`llm_calls.jsonl` records per-call routed model, latency, and finish_reason.
The final-candidate judge tier must be reported separately from any local
substitute judge.
