# Artifact Manifest

Project: Keep, Supersede, or Abstain  
Manifest date: 2026-07-07  
Active codebase: `/Users/ali/Documents/Master/ksa_controller`

This manifest separates inspectable artifacts from smoke, pilot, incomplete,
pending, external-local, and deprecated evidence. Only artifacts marked
`final` or reviewed `final-candidate` may support thesis result tables.

## Status Legend

| Status | Meaning |
|---|---|
| `included` | Present and inspectable in this workspace. |
| `external-local` | Present on this machine outside the package or repo. |
| `smoke` | Small run for code-path validation only. |
| `pilot` | Development or tuning run; not final evidence. |
| `incomplete` | Directory or artifact exists but is not a complete run. |
| `pending` | Planned but not generated. |
| `final-candidate` | Generated with intended final config, pending review. |
| `final` | Approved for thesis table/figure. |
| `deprecated` | Historical artifact retained for provenance only. |

## Core Included Artifacts

| Artifact | Path | Status | SHA-256 | Thesis use |
|---|---|---|---|---|
| Active controller config | `configs/controller_active.yaml` | included | `620188b36d14165566c41e606d56e48bf2211e57488d8a404af830e70cfa10cc` | official config |
| Final LongMemEval policy | `configs/eval_longmemeval_final.yaml` | included | `1723ab8231ae8e858bf4cf690ff1dc17e9893f51737d8afe3f8bb3c3631fdb5a` | planned M4-W13 final-candidate config |
| Final MGP-6 policy | `configs/eval_mgp6_final.yaml` | included | `0da71335fb0fc4972e83f95e0a5784d8d33ef229456b05dd331cb14e32869f5f` | completed M4-W14 final-candidate config |
| Legacy proposal config | `configs/controller_legacy_proposal.yaml` | deprecated | `e7e626fd1a3184049799ab41cb4195d558b932e04d61d67eea08aa601026fae5` | historical tests only |
| MGP-6 v1 | `data/mgp6_v1_seed0.jsonl` | included | `12e17af530067f0ec1cefa1131898e2c8bd2414ef20cfc4c37fb936148e65701` | action-level diagnostic |
| Relation dev100 | `data/dev/relation_dev100_seed0.jsonl` | included | `ee3b0567af825d6b94254a9c29a55336c6e0e9b98bce690dbab153202ebc74e6` | G2 conditional engineering evidence |
| LongMemEval-S 50 slice | `data/slices/longmemeval_s_cleaned_50_seed0.jsonl` | included | `777a8d6fabfd782c05f05267d8af9e7738ad2672dc8626f872209bdc23799831` | smoke/dev slice |

## External-Local Artifacts

| Artifact | Local path | Status | Needed for | Note |
|---|---|---|---|---|
| Cleaned LongMemEval-S source | `/Users/ali/Downloads/longmemeval/longmemeval_s_cleaned.json` | external-local | final LongMemEval-S runs | Regenerate the checked-in 50-slice with `scripts/build_slice.py`. |

## Included Zip Artifacts

| Artifact | Local path | Status | Size | SHA-256 | Contents | Thesis use |
|---|---|---|---:|---|---|---|
| M4-W13 50-item Llama partial B1/B2 zip | `artifacts/m4w13_50_llama/runs(2).zip` | included | 558269 bytes | `72c8656b96f140422b73aaeb150f15e191419eeff6423cb5b5a25be4cac680bb` | `runs/m4w13_50_llama/` with accepted `b1`/`b2`; also contains incomplete `b3`; root manifest `complete=false` | accepted partial baseline provenance only; not an all-system result |
| M4-W13 50-item Llama B3 zip | `artifacts/m4w13_50_llama/runs(3).zip` | included | 4154287 bytes | `3d635ccbc94652706c489df4141dceff4d6f44d095e4e22d3a023137101c4fc5` | `runs/m4w13_50_llama/b3`; root manifest `systems=["b3"]`, `complete=true` | accepted B3 provenance only; not an all-system result |

## Run Outputs

| Run path | Tier | Systems | n | Judge tier | Raw fallback | Complete? | Thesis use |
|---|---|---|---:|---|---|---|---|
| `runs/m1w2/`, `runs/m1w3/`, `runs/m1w4/` | deprecated | early baselines | varies | local dev | false | yes | historical substrate evidence only |
| `runs/m2w7_research_temporal_v2/` | included | relation classifier | 100 | direct label comparison | false | yes | G2 conditional engineering evidence |
| `runs/m2w8/final*` | deprecated | relation classifier | 100 | direct label comparison | false | yes | superseded by repaired G2 caveat |
| `runs/m3w10_smoke/` | smoke | all five systems | small | local dev | false | yes | code path validation only |
| `runs/m3w12/` | included | advisor packet/proxy labels | 12 | internal Codex proxy | false | yes | not external advisor validation |
| `runs/m4w13/` | incomplete | B1 only artifacts present | unknown | Ollama manifest | false | no | no final claim |
| `runs/m4w13_50_llama/` | partial final-candidate | B1-B3 accepted; B4/controller pending | 50 | Ollama `phi3.5:3.8b` | false | partial only | no all-system final claim; included zip provenance in `artifacts/m4w13_50_llama/` |
| `runs/m4w13_light_smoke/` | smoke | B1-B4 + controller | 2 | Ollama local | false | yes | smoke only |
| `runs/m4w13_a10g_sweep/confirm/tk08-rk05-w02-t128-64/` | incomplete | controller config dir only | 50 requested | same_as_answerer | true | no | no final claim |
| `runs/m4w13_a10g_controller_50/` | incomplete | log dir only | 50 requested | same_as_answerer | true | no | no final claim |
| `runs/m4w13_a10g_b4_controller_v2_50/` | incomplete | log dir only | 50 requested | same_as_answerer | true | no | no final claim |
| `runs/m4w13_a100_50/` | incomplete | log dir only | 50 requested | same_as_answerer | true | no | no final claim |
| `runs/m4w13_a100_50_budget/` | incomplete | log dir only | 50 requested | same_as_answerer | true | no | no final claim |
| `runs/m4w13_modal_hf_b1_controller/` | pilot | B1 no-memory + controller | 50 | same_as_answerer `Qwen/Qwen2.5-3B-Instruct` | true | yes by summary; root manifest `complete=false` stale | development comparison only, no final claim |
| `runs/m4w13_final_candidate/` | pending | planned all five systems | 50 | Ollama `phi3.5:3.8b` | false | no | no final claim until complete |
| `runs/lme_m_full_hf_a100_40gb_seed0/` | incomplete | log dir only | unknown | HF/same-model development | true | no | no final LongMemEval claim |
| `runs/_dry_nextgen/`, `runs/_dry_vllm/`, `runs/_dryrun_check/` | smoke | dry-run/check artifacts | varies | none | false | no | command validation only |
| `runs/free_llmapi_cogito_*` | pilot | assorted LongMemEval API/embedder experiments | varies | API or mixed development judges | varies | partial | development evidence only; not final thesis evidence |
| `runs/openai_compat_smoke/` | smoke | OpenAI-compatible backend check | small | API smoke | false | no | backend smoke only |
| `runs/m4w14_thesis_colab_20260608/` | final-candidate | all five systems | 60 | direct MGP-6 labels | false | yes | **VALID MGP-6 evidence**. Controller action accuracy 0.617 vs naive-overwrite 0.517; paired diff CI includes 0; lineage recoverability controller 1.0 vs naive-overwrite 0.0. |
| `runs/m4w15_thesis_colab_20260608/` | final-candidate | MGP-6 RC@C action-log replay | 60 | direct MGP-6 labels | false | yes | **VALID RC@C evidence** derived from `runs/m4w14_thesis_colab_20260608`; report default operating point as headline and sweep as characterization only. |
| `runs/m4w14/` | **INVALID** | all five systems | 60 | direct MGP-6 labels | false | yes | **DO NOT USE** — invalid pre-fix runs; extraction bug caused 46/60 scenarios to be lost. See `NOTES/m4w14_pipeline_audit_2026-05-29.md` and `runs/m4w14/INVALID.md`. |
| `runs/m4w15/` | **INVALID** | MGP-6 RC@C action-log replay | 60 | direct MGP-6 labels | false | yes | **DO NOT USE** — derived from invalid pre-fix `runs/m4w14` action logs; extraction bug caused 46/60 scenarios to be lost. See `runs/m4w15/INVALID.md`. |

## Required Final-Candidate Artifacts

| Artifact | Target path | Status | Blocking issue |
|---|---|---|---|
| Full MGP-6 all-system run | `runs/m4w14_thesis_colab_20260608/` | final-candidate | valid post-fix run; promotion gate not final because controller-vs-B4 diff CI includes 0 |
| Full LongMemEval-S all-system run | `runs/m4w13_50_llama/` | partial | B1/B2/B3 accepted; B4+controller missing unless produced later |
| Modal HF LongMemEval B1/controller pilot | `runs/m4w13_modal_hf_b1_controller/` | pilot | complete for B1/controller only; same-as-answerer judge and raw fallback enabled |
| RC@C curve | `runs/m4w15_thesis_colab_20260608/rc_at_c_curve.png` | final-candidate | generated from valid M4-W14 thesis Colab controller action log |
| External advisor labels | `runs/m3w12/advisor_annotations_external_v1.jsonl` | pending | advisor labels unavailable |

## Current Caveats

- MGP-6 v1 is author-designed and single-annotator unless external labels are added.
- G2 is a conditional engineering pass on a derived relation set, not native benchmark evidence.
- LongMemEval-S supports downstream QA/retrieval diagnostics, not gold action correctness.
- Same-model and HF judge runs are development evidence only.
- MGP-6 stale-active-memory diagnostics (SMRR) are computed by `scripts/evaluate_smrr_mgp6.py`.
- SMRR cannot test H2: it ties the controller with naive overwrite because both clear stale
  items from the active set. H2 (lineage auditability) is tested by
  `superseded_recoverability` (`scripts/evaluate_recoverability_mgp6.py`,
  `ksa.eval.recoverability`): on the valid `runs/m4w14_thesis_colab_20260608`
  run, controller = 1.0 and naive overwrite = 0.0.
- LongMemEval-S SMRR is reportable only where stale retrieval is semantically computed.
- The shipped `runs/m4w13_modal_hf_b1_controller` LongMemEval result (controller 66%) is
  triple-confounded: same-as-answerer judge + `raw_turn_fallback=true` + the extraction bug,
  so the number reflects raw-turn flat retrieval, not the controller's revision policy. Final
  LongMemEval claims require `raw_turn_fallback=false`, all five systems, and a stable judge.
- Accepted LongMemEval-S 50-item status is partial only: B1 = 18%, B2 = 38%, B3 = 22%;
  B4+controller is missing unless a later complete `--require-complete` summary is added.
- MGP-6 transient/context-bound behavior remains a known weak slice unless a later
  deterministic guard and post-change evaluation are documented: T5 transient trap accuracy
  is 0.300 and T6 confidence laundering accuracy is 0.300 in the valid run.
