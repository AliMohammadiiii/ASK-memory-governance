# Invalid, incomplete, and historical evidence

Audit date: 2026-07-13. Raw evidence is preserved read-only, but scientific use is governed by the canonical status column below. The only allowed statuses are final_candidate, diagnostic_only, failure_replay_only, incomplete, invalid, and externally_pending.

## Invalid

| Run | Evidence pointer | Why invalid |
|---|---|---|
| v5 range run | external://Master/ksa_controller/runs/lme_m_openrouter_qwen_gemma_minilm_100_129_seed0_v5/ | Directory name says items 100-129, but the data file contains 200-239; KeyboardInterrupt; only 32/40 shard judgments; no merged report |
| v8 thinking-mode replay | external://Master/ksa_controller/runs/lme_m last version/lme_m_modal_qwen35_9b_v8_failures/ | Zero completed predictions after per-shard MiniLM crashes and thinking-token exhaustion; see INVALID.md |
| MGP-6 smoke family | artifacts/mgp6_v2/*_smoke*/controller/ | Selected report.json files scored only 1 to 10 predictions with a default 180-row denominator; configuration shakedowns are not scientific runs |
| m4w14 and m4w15 | docs/history/ARTIFACT_MANIFEST.md | Pre-fix extraction bug lost 46 of 60 scenarios; historical manifest says not to use |
| m4w13 controller 66 percent | docs/history/ARTIFACT_MANIFEST.md | Same-model judge, raw-turn fallback, and extraction bug are jointly confounded |
| MGP-6 human review sheet | mgp6_v2/review/examples_review_sheet.csv | Zero of 180 rows are filled; a blank template is not evidence |

## Incomplete

| Run | Evidence pointer | Observed state and defensible use |
|---|---|---|
| v8 former-success top-up on Modal | external://Master/ksa_controller/runs/lme_m last version/lme_m_modal_qwen_gemma_minilm_strat30_seed0_v8_topup110/controller/_shards/ | 84/110 completed; 71 correct and 13 regressions. Combined with the completed 70-item replay: raw 96/154 observed; full-180 raw bounds 53.3% to 67.8%; with four replay overrides 55.6% to 70.0%. It decisively contradicts the 77.2% carry-forward construction for this attempt but is not a completed result. |
| v8 former-success top-up on OpenRouter | external://Master/ksa_controller/runs/lme_m last version/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v8_topup110/controller/_shards/ | 3/110 predictions; no merged report |
| MGP-6 six-shot decision baseline | artifacts/results/mgp6_few6_report.json | 174 predictions align to 180 gold IDs; six missing are scored INVALID. Coverage-aware accuracy 0.7833 and macro-F1 0.7692 are an incomplete-run bound, not a completed-system result. |
| Pre-July LongMemEval-S 50-item track | external://Master/ksa_controller/FINAL_OK.json and docs/history/LONGMEMEVAL_B4_TODO.md | B4 and controller were not completed; track was replaced by LongMemEval-M |

For single-session preference in the incomplete v8 attempt, 0/19 replay failures repaired and 8/10 completed former successes remained correct, with one former success unresolved. The observed value is 8/29 and the maximum is 9/30, not the carried-forward 11/30.

## Failure-replay only

| Run | Evidence pointer | Why it cannot support a performance claim |
|---|---|---|
| v8 no-thinking failure replay | external://Master/ksa_controller/runs/lme_m last version/lme_m_modal_qwen35_9b_v8_failures_nothink/controller/report.json | Evaluates exactly the 70 failures used to design the fixes; contexts and judge differ; 25/70 is failure_replay_only |
| Raw carry-forward construction | external://Master/ksa_controller/runs/lme_m last version/lme_m_v8_failure_replay_adjudicated/controller_raw/report.json | 135/180 retains all 110 old successes and replaces only old failures; it omits observed regressions |
| Adjudicated carry-forward construction | external://Master/ksa_controller/runs/lme_m last version/lme_m_v8_failure_replay_adjudicated/controller/report.json | 139/180 = 77.2% adds four post-hoc Codex/GPT-5 overrides to the same selection-biased construction; the incomplete top-up bounds this attempt below 77.2% |

The 75.0% and 77.2% constructions may be named only to document their rejection. They are not KSA LongMemEval results.

## Diagnostic-only development evidence

| Run | Reason |
|---|---|
| v3 10-19 and 20-29 | Small early range probes; 5/10 and 4/10 |
| v4 100-129 | Partial development range; 17/30 |
| v6 200-239 | Partial range used to design later fixes; 29/40 |
| v7 stratified five-system run | Provider/extraction contamination: 316 HTTP-402 traces, 388 empty fallbacks, at least 12 relaunches, and no-op escalation; controller 110/180 and B4 114/180 are diagnostic_only |
| MGP-6 four-model annotation panel | Useful model audit with Fleiss kappa 0.9815, but not human inter-annotator agreement |
| MGP-6 MemOS adapter | Supersession is unobservable through the adapter; 0.144 is a harness bound |

## Externally pending

The frozen final-1.1 homogeneous LongMemEval five-system run has no predictions. The supplied credential returned HTTP 403 before inference. It remains externally_pending until a newly authorized credential is used and the resulting artifact passes the homogeneity and provenance gates.

## Historical-evidence rule

Replaced development evidence is not deleted. It remains available for reconstruction, failure analysis, and audit, but it must not be pooled with final_candidate rows or silently substituted when the externally_pending run is absent. RUN_CLASSIFICATION.csv is authoritative when an older note uses different language.
