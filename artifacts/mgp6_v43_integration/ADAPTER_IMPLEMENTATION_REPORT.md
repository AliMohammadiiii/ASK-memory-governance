# MGP-6 v4.3 system-adapter implementation report

## Result

Commit `c37b8878512cd4125a4beb793dd2a6625c35a9df` implements distinct
public-only v4.3 adapters inside the existing ASK evaluator and runner. The
previous generic-label ambiguity is removed: each registered system now has a
different public model view, prompt policy, deterministic rule policy, or
action-set constraint.

| ID | Logical role | v4.3 behavior | Runtime |
| --- | --- | --- | --- |
| `b1` | no-memory | dialogue/query only; omits `memory_before` | model-backed |
| `b2` | flat retrieval | sorted flat memory rows, no lineage inference | model-backed |
| `b3` | recency | stored value plus last two dialogue turns | model-backed |
| `b4` | overwrite | full public view, restricted to KEEP/SUPERSEDE | model-backed |
| `decision_zero_shot` | decision zero-shot | original full public decision view | model-backed |
| `rules_controller` | rules controller | public requested-value evidence through the ASK scorecard | local deterministic |
| `live_model_controller` | live controller | full public view plus controller policy instruction | model-backed |
| `ablation_no_abstain` | ablation | controller view restricted to KEEP/SUPERSEDE | model-backed |
| `ablation_no_provenance` | ablation | omits speaker and turn IDs | model-backed |
| `ablation_no_typing` | ablation | disables type/stability instruction | model-backed |
| `ablation_no_lineage` | ablation | disables lineage instruction | model-backed |

The adapter version is `ask.mgp6_v43_adapter.v1`. Each view runs
`assert_model_safe` before rendering; labels, component IDs, private IDs,
annotation fields, and hidden gold cannot enter model prompts or raw logs.

## Public development execution: rules controller

The deterministic rules controller was run over all 180 public dev records
after the implementation commit:

- Run directory (ignored): `runs/mgp6_v43/dev/rules_controller_v1_c37b887/`.
- Prediction SHA-256:
  `af9c14a2f3e9b991e9496cd38bbc5d8b0e9faa3d2442e6d6b3f23b92841ba7ed`.
- Manifest code commit: `c37b8878512cd4125a4beb793dd2a6625c35a9df`.
- Manifest tracked worktree state: `clean`.
- 180/180 validated predictions; zero failures, retries, invalid responses, or
  provider calls; `hidden_gold_accessed=false`.
- Accuracy: 0.3333; Macro-F1: 0.2434; coverage: 1.0000.
- Prediction counts: KEEP 0, SUPERSEDE 39, ABSTAIN 141.
- The public scorer intentionally does not read the private component map, so
  it does not compute component-cluster intervals.

This is development evidence only. The rules controller is not selected for a
hidden run. The model-backed B1--B4 adapters subsequently completed public-dev
runs, each with 180/180 validated predictions and zero
failures/retries/invalid responses. Their accuracy / Macro-F1 values were B1:
0.3667 / 0.3150, B2: 0.3556 / 0.2380, B3: 0.3389 / 0.2309, and B4: 0.3444 /
0.2064. Every manifest records `hidden_gold_accessed=false` and a clean tracked
worktree. None is selected for hidden evaluation; see
`DEV_EXPERIMENT_REPORT.md`.

## Verification

- Full repository tests: 539 passed, 11 skipped.
- v4.3-specific tests: 13 passed.
- Ruff, exact CI-scope Mypy (16 files), extended Mypy (63 files), repository
  validation, and package build: PASS.
- The public scoring command rejects missing, duplicate, or unknown predictions
  through the shared strict loader and refuses datasets without public gold.

## Remaining development work

Run the live-model controller and the four model-backed ablations on public dev;
score them with `scripts/score_mgp6_v43.py`, document every selection decision,
and only then freeze the selected configurations. No hidden prediction or
private scoring is authorized.
