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

Install: `pip install -r external/requirements-external.txt`

Every runner: resumable, isolated store per scenario, same answerer backbone
(`MGP6_MODEL`, default qwen/qwen3.5-9b) except Letta (native agent answers,
flagged). Always smoke-test with `--limit 2` first. Outputs both
`predictions.jsonl` (NOOP→KEEP) and `predictions_noop_abstain.jsonl`
(NOOP→ABSTAIN); report both, cite the better as the system's upper bound.
Mapping + rationale: see the docstring in `common.py`.

LongMemEval: `../ksa_controller/scripts/run_external_lme.py` reuses these
adapters with the SAME judge/report machinery as the internal systems.

Framework verified end-to-end with a stub adapter against
`metrics_mgp6.py` (schema-compatible); Mem0/Graphiti adapters are built
against pinned wheels (2.0.11 / 0.29.2); Letta/MemOS are BETA (SDK surfaces
move quickly — check the smoke run before launching the corpus).
