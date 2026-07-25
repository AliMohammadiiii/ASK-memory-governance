# MGP-6 v2 evaluation harness (baselines + controllers)

This adds a runnable evaluation layer on top of the v2 dataset. Everything
scores through the repository's own `metrics_mgp6.py`, so all numbers are
reproducible with that scorer. Answers are judged by regex (`judge_spec`), so
**no LLM judge is required**.

## Systems

| id | what it is |
|---|---|
| `b1` | no-memory sanity floor (stores nothing, never commits) |
| `b2` | flat retrieval, no write governance (keeps the prior value forever) |
| `b3` | recency (newest detected value always wins; no abstain) |
| `b4` | naive overwrite (destructive replace, no lineage, no abstain) |
| `controller` | rule-based governed controller (deterministic, offline) |
| LLM controller | the real model via OpenRouter (default `qwen/qwen3.5-9b`) |

All memory-using offline systems share one deterministic text extractor
(`systems/extractor.py`, ~82% candidate-value recall) so the comparison
isolates *write governance*, not extraction. The LLM controller does its own
extraction and answering.

## Run the offline five systems (no API key, no GPU)

```bash
bash deploy/run_mgp6_v2_5systems.sh
# -> runs/ref_5systems/{b1,b2,b3,b4,controller}/{predictions.jsonl,report.json}
# -> runs/ref_5systems/ANALYSIS.md , summary.json , comparison.json
```

## Run the real LLM controller (needs an API key)

```bash
export OPENROUTER_API_KEY=sk-or-...
bash deploy/run_mgp6_v2_llm.sh          # resumable; safe to interrupt/rerun
# -> runs/llm_qwen35_9b/controller/{predictions.jsonl,report.json}
# -> runs/combined/ANALYSIS.md , comparison.json   (all six systems together)
```

Swap the model with `MGP6_MODEL=...` (any OpenAI-compatible chat model). The
judge model is irrelevant to MGP-6 v2 scoring.

## Files

- `systems/extractor.py` - shared closed-book evidence extractor + governance cues.
- `systems/policies.py` - the five offline systems (B1-B4 + rule controller).
- `run_5systems.py` - offline driver (predictions + per-system metrics + summary).
- `run_llm_controller.py` - resumable, concurrent LLM controller runner.
- `analyze_5systems.py` / `analyze_all.py` - Markdown + JSON report generators.
- `deploy/run_mgp6_v2_5systems.sh`, `deploy/run_mgp6_v2_llm.sh` - one-command wrappers.

## Caveats

- `over_forgetting_rate` / `under_forgetting_rate` saturate at ~1.0 for every
  system in the shipped `metrics_mgp6.py` (it compares the full `slot = value`
  text against the canonicalised value). They are dropped from the headline
  tables; raw values stay in each `report.json`.
- The offline systems are reference implementations to exercise the harness and
  provide a governance floor/ceiling, not the production ASK controller.
