# Paper claims → evidence matrix

Updated 2026-07-27 after the MGP-6 v4.3 and LongMemEval V12 audits. Raw
predictions, judgments, and action logs outrank narrative reports.

| # | Claim in paper | Strength and boundary | Primary evidence |
|---|---|---|---|
| P1 | ASK specifies KEEP / SUPERSEDE / ABSTAIN over typed, provenance-bearing state with retained supersession lineage. | verified reference implementation; runtime realizes a narrower log and SQLite transition path; no priority claim | `src/ask/protocol/`; `tests/test_ask_protocol.py`; `src/ask/memory/operations.py`; `src/ask/pipeline/orchestrator.py` |
| P2 | The V12 runtime evaluates each candidate on `(c,e,f,r,rho)` and the published rule exactly replays both scores and all 12,654 actions. | verified mechanism, not write-label accuracy | `runs_local/lme_final_controller_v12_qwen_180/controller/action_log.jsonl`; `artifacts/analysis/lme_v12_scorecard_analysis.json` |
| P3 | Leave-one-dimension-out replay changes 8 / 0 / 779 / 483 / 0 actions for `c/e/f/r/rho`; removing the relation guard changes 11,091 KEEP decisions to SUPERSEDE. | deterministic counterfactual on the fixed log; not causal/retrained-system evidence | `scripts/analysis/analyze_lme_scorecard.py`; scorecard analysis JSON |
| P4 | Stable, episodic, and transient memories have different observed action profiles, but common thresholds change only five decisions and a common stability prior changes none. | verified descriptive; does not validate the hand-set type policy | scorecard analysis JSON `observed.by_memory_type`, `mechanism.type_channels` |
| P5 | MGP-6 v4.3 contains 900 controlled synthetic items in 100 nine-item semantic components, split by component and exactly action-balanced. | verified artifact description; not a population benchmark or publicly licensed dataset release | `benchmarks/mgp6/mgp6_v4_3/public/`; manifests and integration reports |
| P6 | The single configuration frozen before hidden scoring reaches 0.8481 accuracy / 0.8479 macro-F1 with component-cluster intervals `[0.8037,0.8889]` / `[0.8021,0.8894]`. | final hidden result for one configuration; no hidden comparison | `runs/mgp6_v43/final_hidden/`; `artifacts/analysis/mgp6_v43_full_benchmark_analysis.json` |
| P7 | On hidden, 30 of 38 gold-ABSTAIN errors are state-preserving KEEP decisions; 8 are state-corrupting SUPERSEDE decisions (0.0444, CI `[0.0227,0.0852]`). | verified operational decomposition | hidden predictions + v4.3 benchmark-analysis JSON |
| P8 | On public development, the composed controllers are above chance while structural baselines, the scorecard adapter, ablations, and adapter-mapped external systems are near chance. | development-only, selected-on split; external rows mapping-dependent | `runs/benchmark_suite/v43_public_dev_complete_qwen35_9b/`; external dev runs; analysis JSON |
| P9 | Neither the model action nor public-evidence rule action alone exceeds 0.750 on v4.3 development; their frozen composition reaches 0.8444. | verified development component decomposition, not hidden | v4.3 raw response `guard_trace` fields; `tables/v43_guard.tex` |
| P10 | The LongMemEval V12 final candidate reaches 137/180 (76.1%) versus naive overwrite 114/180 (63.3%), paired Holm-corrected `p=2.9e-4`. | verified one-slice downstream result; one answer model and judge; stale launcher hash and nonterminal historical manifest remain | `runs_local/lme_final_controller_v12_qwen_180/`; `reports/RESULTS_LME_FINAL.md` |
| P11 | Extraction and relation classification consume 92.8% of V12 prompt tokens and 99.4% of model calls; answer generation is 7.2% of prompt tokens. | verified trace accounting; provider telemetry, not hardware compute | extraction/relation traces and V12 answer records; full benchmark-analysis JSON |
| P12 | Conflict type alone reaches 1.000 held-out v2 action accuracy; type alone reaches 0.9667. | verified construct failure; invalidates v2 capability interpretation | `artifacts/analysis/mgp6_validity_audit.json` |
| P13 | The v2 no-lineage ablation leaves action accuracy 0.9222 but lowers lineage integrity 0.8556→0.3689. | verified within-generator measurement demonstration | `artifacts/mgp6_v2/ablations/` |
| P14 | Contaminated v7 and the 77.2% carry-forward construction are ineligible; V12 supersedes them. | verified provenance classification | `docs/audit/CONTROLLERRUN_*`; experiment/evidence registries |
| P15 | The V12 computation helper recognized 28 controller and 39 naive-overwrite items, bypassed the answer model zero times, and made two controller substitutions: one repair and one regression, for zero net accuracy change. | verified answer-layer trace; not a source of the controller's aggregate gain | V12 `controller/answers.jsonl`, `b4/answers.jsonl`, and judgments |

## Claim guardrails

- The five-feature scorecard generated the LongMemEval V12 write decisions, not
  the MGP-6 v2 lexical-reference predictions or the MGP-6 v4.3 hidden
  predictions.
- Exact scorecard replay proves execution fidelity, not correctness or
  optimality. LongMemEval has no gold write action per extracted candidate.
- The deterministic v4.3 development row at 0.3333 is the scorecard adapter;
  the 0.750 rule component is the distinct public-indexed-evidence policy inside
  the composed controller.
- No baseline, ablation, successor, external system, or component was scored on
  the v4.3 sealed hidden split. All such contrasts are development evidence.
- External-system results always retain adapter/mapping disclosure.
- V4.3 is a controlled synthetic diagnostic, not a community benchmark,
  deployment-safety test, or population sample.
- V2 human evidence (one independent annotator plus a four-model panel) must
  not be conflated with v4.3's two owner-attested annotation packets.
- The deterministic computation helper is an answer-layer component, not part
  of the five-dimensional write rule; its V12 substitutions were net neutral.
- No claim of priority is made for write actions, abstention, typed memory,
  provenance, lineage, operation-level evaluation, or “memory governance.”
- The generic ASK validator and transition-event schema are tested reference
  components; the V12 SQLite mutation path does not invoke or emit them.
- MGP-Natural v0.1.0 and v0.2.2 are quarantined feasibility/construction
  artifacts. Neither supplies independent gold or a paper performance result.
