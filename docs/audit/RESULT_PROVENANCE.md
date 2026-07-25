# Result provenance

Audit date: 2026-07-13. Quantitative authority is artifacts/results_ledger.json. Run status is governed by RUN_CLASSIFICATION.csv. External evidence roots are bound by tree digests in artifacts/manifests/source_archives.json.

## MGP-6 v2

| Value | Claim status | Evidence chain |
|---|---|---|
| Conflict-type lookup 1.0000 / 1.0000 on test 90 | diagnostic_only; construct gate failed | artifacts/analysis/mgp6_validity_audit.json ← train+development lookup evaluated on test ← benchmarks/mgp6/data/mgp6_v2.jsonl |
| Rule controller 0.9222 accuracy / 0.9399 macro-F1 on full 180 | diagnostic_only; full corpus includes train/development | artifacts/mgp6_v2/ref_5systems/controller/report.json ← predictions.jsonl with 180 rows ← metrics_mgp6.py ← benchmarks/mgp6/data/mgp6_v2.jsonl |
| Rule controller 0.8889 / 0.9145 on test 90 | diagnostic_only; construct gate failed | test block of the same canonical report plus artifacts/analysis/mgp6_validity_audit.json |
| Qwen 3.5 9B controller 0.8889 / 0.8913 | diagnostic_only; construct gate failed | artifacts/mgp6_v2/llm_qwen35_9b/controller/report.json ← run_llm_controller.py |
| Zero-shot decision 0.7000 / 0.6657 | diagnostic_only; construct gate failed | artifacts/mgp6_v2/llm_decision_zero/controller/report.json ← run_llm_decision_baseline.py |
| Six-shot coverage-aware 0.7833 / 0.7692 | incomplete | artifacts/results/mgp6_few6_report.json, SHA-256 eed881c69185902b5c892c8f8c6b4ac3e045d081abfc44f9e9eb8a9649f8aeaa ← 174 source predictions aligned to 180 gold IDs; six missing IDs scored INVALID |
| Ablation values | diagnostic_only; within-generator mechanism evidence | artifacts/mgp6_v2/ablations/VARIANT/report.json plus ablation_summary.json ← run_ablations.py |
| Letta 0.678; Mem0 0.622; Graphiti 0.383 under NOOP-to-ABSTAIN | diagnostic_only; mapping-dependent | artifacts/mgp6_v2/ext_SYSTEM/controller/report_noop_abstain.json ← external adapter runner and adapter_meta.json; companion NOOP-to-KEEP reports must also be disclosed |
| MemOS 0.144 harness bound | diagnostic_only | artifacts/mgp6_v2/ext_memos/controller/report_noop_abstain.json; adapter cannot expose supersession |
| Independent annotator raw agreement 0.9889 and Cohen kappa 0.98146 | diagnostic label audit | benchmarks/mgp6/annotations/human/human_annotation_agreement_summary.json ← 90-item test annotation; one annotator only |
| Four-model Fleiss kappa 0.9815 | diagnostic_only | mgp6_v2/annotation/geminiPro.csv, gptSolHigh.csv, kimi.csv, and z.csv ← 90 items per model; this is model-audit evidence |

MGP-6 dataset identity: 180 rows, 381,119 bytes, SHA-256 870705e71170026fc2e75dcc5b275f9a99ca3cc5501f054c2ac0d1a013b4a583.

## LongMemEval-M

The 180-item slice is deterministic seed-0 sampling of 30 examples from each of six competencies. It is 950,452,379 bytes with SHA-256 f10b4fb4173d3e2d9310d90c2b6bf8f5e7b147cea1d04affa9037b1b9fe6787d and is not redistributed.

| Value | Claim status | Evidence chain and interpretation |
|---|---|---|
| v7 controller 110/180 post-adjudication; 108/180 before | diagnostic_only | external://Master/ask_controller/runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v7/controller/report.json and pre_adjudication originals; contaminated by provider and extraction failures |
| v7 B4 114/180; B2 80/180; B3 43/180; B1 9/180 | diagnostic_only | same v7 external tree under b4, b2, b3, and b1 report.json files |
| v8 no-thinking replay 25/70 | failure_replay_only | external://Master/ask_controller/runs/lme_m last version/lme_m_modal_qwen35_9b_v8_failures_nothink/controller/report.json; exactly the prior 70 v7 failures |
| v8 top-up 71/84 with 13 regressions | incomplete | external://Master/ask_controller/runs/lme_m last version/lme_m_modal_qwen_gemma_minilm_strat30_seed0_v8_topup110/controller/_shards/; 84 of 110 former-success items completed |
| combined observed raw 96/154 | incomplete | 71 top-up-correct plus 25 replay-correct over 84 plus 70 observed items |
| full-180 raw bound 53.3% to 67.8% | incomplete | unresolved 26 items assigned all incorrect or all correct: 96/180 to 122/180 |
| full-180 adjudicated bound 55.6% to 70.0% | incomplete | same bound after adding the four replay overrides: 100/180 to 126/180 |
| single-session preference observed 8/29; maximum 9/30 | incomplete | top-up retained 8/10 completed former successes; replay repaired 0/19 failures; one former success unresolved |
| raw replay construction 135/180 = 75.0% | failure_replay_only | external://Master/ask_controller/runs/lme_m last version/lme_m_v8_failure_replay_adjudicated/controller_raw/report.json ← all 110 v7 successes carried forward plus 25 replay repairs |
| adjudicated replay construction 139/180 = 77.2% | failure_replay_only | sibling controller/report.json ← raw construction plus four Codex/GPT-5 overrides; contradicted by the top-up regressions and not an observed homogeneous run |
| final-1.1 five-system result | externally_pending | configs/release/final.yaml and FINAL_EVALUATION_PROTOCOL.md; API request returned HTTP 403 before inference, so no predictions or accuracy exist |

The v8 external tree is bound by SHA-256 tree digest 6e10915aefb613305af70e7fda83764fde03e7bc0c892de9556476fae09b3d4d. The v7 tree is bound by 9023a31b72a20d140f768d8cae3ecd3df14d1d337a296227c3cb2befcb5c7666. See INPUT_INVENTORY.md for the hash method.

## Known provenance defects

1. The historical adjudicated manifest names a replay directory that does not exist. The actual completed replay is external://Master/ask_controller/runs/lme_m last version/lme_m_modal_qwen35_9b_v8_failures_nothink. The original evidence is preserved; artifacts/controller_run_comparison.json records the corrected mapping.
2. The 139/180 construction labels four Codex/GPT-5 decisions as human adjudication in historical records. They are machine-assisted semantic overrides and are described that way in the canonical audit.
3. Replay contexts differ from v7 contexts, so a cross-version item outcome does not isolate the answer model or memory policy as the cause.
4. The narrative file external://Master/MGP6_LongMemEval_Final_Report_EN.md is a secondary source. Where it conflicts with the ledger or top-up evidence, the ledger wins.

## Recalculation rules

- Never infer a completed denominator from a report filename; verify IDs and line counts.
- Keep raw machine judgments separate from overrides.
- Do not carry prior successes into a new-method total unless those items were rerun under the same frozen configuration.
- Do not pool rows with different judges without per-item provenance and an explicit heterogeneity analysis.
- A run's historical `final_candidate` label is necessary but not sufficient for a main result: later construct-validity evidence can supersede claim eligibility. Current MGP-6 v2 rows are diagnostic; other values require their exact status and limitation.
