# External memory-system baselines

Published memory systems evaluated on MGP-6 v2 through their **native write
paths**, per the protocol: scored on **action** (documented observation→action
mapping) and **answer** metrics; artifact/lineage reported as **N/A**.

| System | Paper | Runner | Needs |
|---|---|---|---|
| Mem0 | Chhikara et al. 2025 (arXiv:2504.19413) | `run_mem0.py` | OPENROUTER_API_KEY |
| Zep/Graphiti | Rasmussen et al. 2025 (arXiv:2501.13956) | `run_graphiti.py` | key + local embeddings server |
| Letta (MemGPT) | Packer et al. 2023 (arXiv:2310.08560) | `run_letta.py` | Docker letta server (BETA) |
| MemOS | Li et al. 2025 (arXiv:2507.03724) | `run_memos.py` | key via OPENAI_* env (BETA) |

Install these research-only adapters in a dedicated environment as documented
in `external/requirements-external.txt` and the exact
`../../../constraints/external-baselines-py312.txt` lock. Do not combine that environment with
the maintained `.[ml]` extra because MemoryOS requires an older Transformers
major version. Use only recorded model sources, provide no production secrets,
and treat the environment as untrusted after loading external checkpoints.

Every runner: resumable, isolated store per scenario, same answerer backbone
(`MGP6_MODEL`, default qwen/qwen3.5-9b) except Letta (native agent answers,
flagged). Always smoke-test with `--limit 2` first. Outputs both
`predictions.jsonl` (NOOP→KEEP) and `predictions_noop_abstain.jsonl`
(NOOP→ABSTAIN); report both, cite the better as the system's upper bound.
Mapping + rationale: see the docstring in `common.py`.

### ASK-controller alignment

The public v4.3 wrapper aligns every configurable external backend with the
frozen ASK controller: OpenRouter Qwen 3.5 9B, temperature zero where the
backend exposes decoding controls, and the CPU
`sentence-transformers/all-MiniLM-L6-v2` 384-dimensional embedder.  Set the
shared values once with `MGP6_MODEL`, `MGP6_BASE_URL`, `MGP6_EMBED_MODEL`,
`MGP6_EMBED_DIM`, and `MGP6_EMBED_BASE_URL`; Graphiti and MemOS use the shared
OpenAI-compatible embedding server, while Mem0 loads the same MiniLM weights
locally.  Letta's evaluated core-memory-block path performs no vector
retrieval, so its embedding setting is not applicable; its model handle is
derived as `openai-proxy/$MGP6_MODEL`.

Native write/tool loops are not ASK controller decisions. Their operational
token budgets remain backend-specific and are recorded in the run metadata;
forcing the controller's 128-token action limit on them produces truncated
tool calls and invalidates the backend run.

LongMemEval: `../ask_controller/scripts/run_external_lme.py` reuses these
adapters with the SAME judge/report machinery as the internal systems.

Framework verified end-to-end with a stub adapter against
`metrics_mgp6.py` (schema-compatible); Mem0/Graphiti adapters are built
against pinned wheels (2.0.11 / 0.29.2); Letta/MemOS are BETA (SDK surfaces
move quickly, check the smoke run before launching the corpus).

## MGP-6 v4.3 public-development integration

`scripts/run_mgp6_v43_external.py` drives these same adapters only with the
public v4.3 model input. It isolates every record under
`mgp6-v43:<public_id>`, records native write observations and retrieval, then
emits a **derived action from observable state**. This is not a native action
reported by any backend. v4.3 has action labels but no reference natural-
language answer, so native-answer accuracy is deliberately not claimed.

Run one smoke test (public data only):

```bash
.venv/bin/python scripts/run_mgp6_v43_external.py \
  --backend mem0 \
  --input benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl \
  --out runs/mgp6_v43_external/dev/mem0 \
  --limit 2
```

Or add all four backends to the parallel public suite after installing their
pinned dependencies and starting the required Graphiti/Letta/MemOS services:

```bash
.venv/bin/python scripts/run_benchmark_suite.py \
  --execute-external-backends --max-parallel 4 --resume
```

Neither command accepts hidden input or hidden gold. Score only public train
or dev results with `scripts/score_mgp6_v43.py`; final hidden evaluation needs
its separately frozen authorization process.
