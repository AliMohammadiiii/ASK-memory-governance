# M4-W13 Modal HF B1/Controller Pilot Status

Date received: 2026-05-29

Source zip: `/Users/ali/Downloads/ask_modal_results.zip`

Imported run path: `runs/m4w13_modal_hf_b1_controller/`

## Status

This is a complete Modal/HF pilot for B1 no-memory and the controller on 50
LongMemEval-S cleaned items. It is not final thesis evidence because the run
uses `judge_backend=same_as_answerer` and `raw_turn_fallback=true`.

## Summary

| System | n | Accuracy | 95% CI | Judge | Raw fallback | Thesis use |
|---|---:|---:|---|---|---|---|
| B1 no-memory | 50 | 0.0% | 0.0%-0.0% | `Qwen/Qwen2.5-3B-Instruct` | true | pilot only |
| Controller | 50 | 66.0% | 52.0%-78.0% | `Qwen/Qwen2.5-3B-Instruct` | true | pilot only |

## Diagnostics

- Controller action log rows: 408.
- Controller extraction trace rows: 400.
- Controller relation trace rows: 257.
- Controller action counts: Keep 284, Supersede 13, Abstain 111.
- Current-session leakage: 0 for both B1 and controller.

## Manifest Note

The run-level `manifest.json` still has `complete=false`, but
`summary.json` reports both listed systems complete and `missing_systems=[]`.
The artifact manifest records this as a complete pilot with a stale root
completion flag.
