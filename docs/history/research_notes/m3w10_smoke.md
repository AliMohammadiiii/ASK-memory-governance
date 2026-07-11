# M3-W10 Smoke: Controller Wiring + Baseline 4

Date: 2026-05-21

## Scope

This smoke validates the M3-W10 wiring on a five-session LongMemEval-shaped
fixture at `runs/m3w10_smoke/smoke5.jsonl`.

Models used through local Ollama:

- Answerer and judge: `gemma4:e4b`
- Extractor: `llama3.2:3b`
- Relation classifier: `phi3.5:3.8b`

The extractor/classifier pair is identical for B4 and the controller. The only
policy difference is destructive overwrite versus scorecard controller with
lineage-preserving `supersede()`.

## Commands

```bash
source .venv/bin/activate

python scripts/run_baseline.py --baseline no_memory \
  --slice runs/m3w10_smoke/smoke5.jsonl --out runs/m3w10_smoke/no_memory \
  --seed 0 --limit 5 --n-bootstrap 10 \
  --ollama --ollama-model gemma4:e4b --ollama-judge-model gemma4:e4b

python scripts/run_baseline.py --baseline flat_vector \
  --slice runs/m3w10_smoke/smoke5.jsonl --out runs/m3w10_smoke/flat_vector \
  --seed 0 --limit 5 --n-bootstrap 10 --fake-embedder \
  --ollama --ollama-model gemma4:e4b --ollama-judge-model gemma4:e4b

python scripts/run_baseline.py --baseline recency \
  --slice runs/m3w10_smoke/smoke5.jsonl --out runs/m3w10_smoke/recency \
  --seed 0 --limit 5 --n-bootstrap 10 --fake-embedder \
  --ollama --ollama-model gemma4:e4b --ollama-judge-model gemma4:e4b

python scripts/run_baseline.py --baseline naive_overwrite \
  --slice runs/m3w10_smoke/smoke5.jsonl --out runs/m3w10_smoke/naive_overwrite \
  --seed 0 --limit 5 --n-bootstrap 10 --fake-embedder \
  --ollama --ollama-model gemma4:e4b --ollama-judge-model gemma4:e4b \
  --extractor-ollama-model llama3.2:3b --classifier-ollama-model phi3.5:3.8b

python scripts/run_baseline.py --baseline controller \
  --slice runs/m3w10_smoke/smoke5.jsonl --out runs/m3w10_smoke/controller \
  --seed 0 --limit 5 --n-bootstrap 10 --fake-embedder \
  --ollama --ollama-model gemma4:e4b --ollama-judge-model gemma4:e4b \
  --extractor-ollama-model llama3.2:3b --classifier-ollama-model phi3.5:3.8b
```

## Results

| Run | Accuracy | Wall-clock | Action counts | Current-session leakage |
|---|---:|---:|---|---:|
| B1 no-memory | 0.80 | 46.54 s | n/a | 0/5 |
| B2 flat-vector | 0.80 | 56.25 s | n/a | 0/5 |
| B3 recency | 0.80 | 45.98 s | Keep=1 | 0/5 |
| B4 naive-overwrite | 0.80 | 276.18 s | Keep=5, Supersede=1 | 0/5 |
| Controller | 0.80 | 274.97 s | Keep=4, Supersede=1, Abstain=1 | 0/5 |

All B4 and controller `action_log` rows validate via `ActionLogRecord`.

## Decision Walk-Throughs

KEEP example:

```text
candidate="I prefer coffee in the morning."
controller rationale="c=1.000, e=0.421, f=0.000, r=0.000 (independent), rho=0.900; S_rev=1.787 above θ_sup=0.900 for stable_pref; S_abs=0.000 below θ_abs=0.600; keep."
```

SUPERSEDE example:

```text
candidate="I now prefer green tea in the morning instead of coffee."
prior_memory_id=1, resulting_memory_id=2
controller rationale="c=1.000, e=1.000, f=0.000, r=-1.000 (contradict), rho=0.900; S_rev=1.050 above θ_sup=0.900 for stable_pref; S_abs=-1.000 below θ_abs=0.600; supersede."
B4 rationale="naive overwrite: relation=supersede; deleted prior id=1 and inserted candidate id=1; no supersession lineage."
```

ABSTAIN example:

```text
candidate="I do not want sparkling water."
controller rationale="c=1.000, e=0.736, f=1.000, r=0.000 (independent), rho=0.900; S_rev=1.339 above θ_sup=0.900 for stable_pref; S_abs=1.000 above θ_abs=0.600; abstain."
```

## Manual Rationale Inspection

Inspected 10 rows from:

- `runs/m3w10_smoke/controller/action_log.jsonl`, rows 1-6
- `runs/m3w10_smoke/naive_overwrite/action_log.jsonl`, rows 1-4

The controller rows include all five feature values, both scores, both
thresholds, the action, and a legible natural-language rationale. B4 rows are
also legible and explicitly state when a prior was deleted without lineage.

## Anti-Leakage

Controller retrieval telemetry:

```text
current_session_leakage_count per session = [0, 0, 0, 0, 0]
retrieved_session_ids = ["m3w10-s001"]
```

The controller builds answer-time retrieval from supporting sessions before it
processes the current session. Current-session candidates are logged after the
answer prompt is rendered, so they do not surface in retrieval. The smoke
passes the anti-leakage check: 0/5 sessions leaked current-session memory.

## Notes

`gemma4:e4b` did not reliably follow the frozen extraction schema on the first
attempt. The smoke therefore uses `llama3.2:3b` for extraction and
`phi3.5:3.8b` for classification, both through real Ollama. This matches the
M2 evidence: `llama3.2:3b` produced usable extraction JSON, and
`phi3.5:3.8b` is the G2-passing relation classifier model.
