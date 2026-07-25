# Repository tree

```text
ask-memory-governance/
├── .github/
│   └── workflows/
│       └── ci.yml
├── artifacts/
│   └── manifests/
│       ├── README.md
│       ├── repository_files.json
│       ├── source_archives.json
│       └── VALIDATION_REPORT.md
├── benchmarks/
│   ├── longmemeval/
│   │   └── README.md
│   ├── mgp6/
│   │   ├── annotation_kit_test/
│   │   │   ├── annotation_sheet.csv
│   │   │   ├── blind_scenarios.jsonl
│   │   │   └── INSTRUCTIONS.md
│   │   ├── annotations/
│   │   │   ├── human/
│   │   │   └── model_or_mixed/
│   │   ├── data/
│   │   │   ├── mgp6_v2.jsonl
│   │   │   └── mgp6_v2.txt
│   │   ├── deploy/
│   │   │   ├── run_mgp6_v2_5systems.sh
│   │   │   └── run_mgp6_v2_llm.sh
│   │   ├── external/
│   │   │   ├── __init__.py
│   │   │   ├── common.py
│   │   │   ├── README.md
│   │   │   ├── requirements-external.txt
│   │   │   ├── run_graphiti.py
│   │   │   ├── run_letta.py
│   │   │   ├── run_mem0.py
│   │   │   └── run_memos.py
│   │   ├── review/
│   │   │   └── examples_review_sheet.csv
│   │   ├── scripts/
│   │   │   └── run_graphiti_fast.sh
│   │   ├── systems/
│   │   │   ├── __init__.py
│   │   │   ├── extractor.py
│   │   │   └── policies.py
│   │   ├── __init__.py
│   │   ├── analyze_5systems.py
│   │   ├── analyze_all.py
│   │   ├── annotation_manual_v2.md
│   │   ├── CHANGELOG.md
│   │   ├── compute_agreement_v2.py
│   │   ├── dataset_card.md
│   │   ├── EVAL_HARNESS.md
│   │   ├── make_annotation_kit.py
│   │   ├── metrics_mgp6.py
│   │   ├── mgp6_schema_v2.py
│   │   ├── mgp6_v2_spec.md
│   │   ├── README.md
│   │   ├── run_5systems.py
│   │   ├── run_ablations.py
│   │   ├── run_llm_controller.py
│   │   ├── run_llm_decision_baseline.py
│   │   ├── run_model_sweep.sh
│   │   └── validate_mgp6.py
│   └── __init__.py
├── configs/
│   ├── models/
│   │   └── openrouter_qwen_gemma.yaml
│   ├── controller_active.yaml
│   ├── controller_legacy_proposal.yaml
│   ├── eval_longmemeval_final.yaml
│   ├── eval_mgp6_final.yaml
│   ├── inference-local.yaml
│   ├── inference.yaml
│   └── m4w13-ollama.yaml
├── data/
│   ├── mgp6_advisor_subsample_v1.jsonl
│   ├── mgp6_v1_seed0.jsonl
│   └── README.md
├── deploy/
│   ├── build_full_slice.sh
│   ├── COLAB_M4W13_50_RUNBOOK.md
│   ├── COLAB_M4W13_T4_RUNBOOK.md
│   ├── COLAB_MGP6_T4_RUNBOOK.md
│   ├── colab_prepare.sh
│   ├── COLAB_README.md
│   ├── colab_requirements.txt
│   ├── download_longmemeval_s.py
│   ├── pull_models.sh
│   ├── replay_v7_controller_failures_modal.sh
│   ├── requirements_nextgen.txt
│   ├── run_a100_40gb_hf_final.sh
│   ├── run_a100_40gb_hf_nextgen.sh
│   ├── run_a100_40gb_hf_server.sh
│   ├── run_colab_full_m4_light.sh
│   ├── run_colab_lme_full.sh
│   ├── run_colab_m4w13_50_cache.sh
│   ├── run_colab_m4w13_a10g_ollama.sh
│   ├── run_colab_m4w13_hf_a100_budget.sh
│   ├── run_colab_m4w13_hf_a100_parallel.sh
│   ├── run_colab_m4w13_hf_a10g_controller.sh
│   ├── run_colab_m4w13_hf_controller.sh
│   ├── run_colab_m4w13_light.sh
│   ├── run_colab_m4w13_one_system.sh
│   ├── run_colab_m4w13_serial_final.sh
│   ├── run_colab_m4w13_t4_ollama.sh
│   ├── run_colab_mgp6_t4.sh
│   ├── run_colab_modal_range.sh
│   ├── run_eval.sh
│   ├── run_lme_m_strat30_5systems.sh
│   ├── run_lme_m_strat30_controller.sh
│   ├── run_lme_v8_full_5systems.sh
│   ├── run_lme_v8_topup110.sh
│   ├── run_on_server.sh
│   ├── serve.sh
│   ├── serve_vllm.sh
│   └── setup_colab_modal_range.sh
├── docs/
│   ├── figures/
│   │   ├── figure_04_annotation_agreement.png
│   │   ├── figure_04_annotation_agreement.svg
│   │   ├── figure_06_evaluation_causal_chain.png
│   │   ├── figure_06_evaluation_causal_chain.svg
│   │   ├── figure_07_ask_controller_architecture.png
│   │   ├── figure_07_ask_controller_architecture.svg
│   │   └── manifest.json
│   ├── history/
│   │   ├── change_notes/
│   │   │   ├── FIXES_2026-05-30.md
│   │   │   ├── FIXES_2026-06-08.md
│   │   │   ├── FIXES_2026-06-10.md
│   │   │   ├── FIXES_2026-06-11.md
│   │   │   └── FIXES_2026-07-08.md
│   │   ├── research_notes/
│   │   │   ├── env.md
│   │   │   ├── eval_protocol.md
│   │   │   ├── finalize_m1w1.md
│   │   │   ├── G1_gate_decision.md
│   │   │   ├── G2_dataset_repair_options.md
│   │   │   ├── G2_gate_decision.md
│   │   │   ├── gap_audit_m1w1.md
│   │   │   ├── INDEX.md
│   │   │   ├── inference_bench.md
│   │   │   ├── longmemeval_mapping.md
│   │   │   ├── m1w2_results.md
│   │   │   ├── m1w2_sanity.md
│   │   │   ├── m1w3_design.md
│   │   │   ├── m1w3_results.md
│   │   │   ├── m1w3_sanity.md
│   │   │   ├── m1w3_sanity.template.md
│   │   │   ├── m1w3_win_loss.md
│   │   │   ├── m1w4_design.md
│   │   │   ├── m1w4_evaluator_drift.md
│   │   │   ├── m1w4_results.md
│   │   │   ├── m1w4_sanity.md
│   │   │   ├── m1w4_sanity.template.md
│   │   │   ├── m1w4_win_loss.md
│   │   │   ├── m2w5_design.md
│   │   │   ├── m2w5_iteration_log.md
│   │   │   ├── m2w5_lit.md
│   │   │   ├── m2w5_sanity.md
│   │   │   ├── m2w5_summary.md
│   │   │   ├── m2w6_adjudication.md
│   │   │   ├── m2w6_annotation_manual_draft.md
│   │   │   ├── m2w6_dataset_repair_from_deep_research.md
│   │   │   ├── m2w7_errors.md
│   │   │   ├── m3w10_smoke.md
│   │   │   ├── m3w11_provenance.md
│   │   │   ├── m3w11_selfreview.md
│   │   │   ├── m3w12_agreement.md
│   │   │   ├── m3w9_design.md
│   │   │   ├── m4_judge_substitution.md
│   │   │   ├── m4w13_50_llama_b1_b2_b3_audit.md
│   │   │   ├── m4w13_50_t4_controller_partial_answer_analysis.md
│   │   │   ├── m4w13_50_t4_quality_analysis_and_roadmap.md
│   │   │   ├── m4w13_a10g_prompt_slim_analysis.md
│   │   │   ├── m4w13_final_policy.md
│   │   │   ├── m4w13_modal_hf_b1_controller_status.md
│   │   │   ├── m4w13_runs.md
│   │   │   ├── m4w13_scaleup_500_and_M.md
│   │   │   ├── m4w14_mgp6_results.md
│   │   │   ├── m4w14_pipeline_audit_2026-05-29.md
│   │   │   ├── m4w14_thesis_colab_20260608_review.md
│   │   │   ├── m4w15_runbook.md
│   │   │   ├── m4w16_runbook.md
│   │   │   ├── role_based_cascade_vllm_standard.md
│   │   │   ├── run_local_smoke.md
│   │   │   ├── status_m1w1.md
│   │   │   ├── status_m1w2.md
│   │   │   └── status_m1w3.md
│   │   ├── ARTIFACT_MANIFEST.md
│   │   ├── CHANGELOG_scaleup_500_M.md
│   │   ├── DEBUG_README.md
│   │   ├── FINAL_TEST_README.md
│   │   ├── GPU_RUN_COMMANDS.md
│   │   ├── LONGMEMEVAL_B4_TODO.md
│   │   ├── V7_FIXES_AND_RUN.md
│   │   ├── V8_FIXES_AND_RUN.md
│   │   └── VERIFY_v6_FAILURES.md
│   ├── annotation_manual.md
│   ├── architecture.md
│   ├── evaluation_protocol.md
│   ├── external_adapters.md
│   ├── known_limitations.md
│   ├── release_checklist.md
│   ├── reproduce_results.md
│   ├── reproducibility.md
│   └── thesis_readiness_audit.md
├── paper/
│   └── README.md
├── prompts/
│   ├── extraction_v0.j2
│   ├── extraction_v1.j2
│   ├── extraction_v2.j2
│   ├── extraction_v3.j2
│   ├── extraction_v_final.j2
│   ├── extraction_v_final2.j2
│   ├── extraction_v_final3.j2
│   ├── relation_stage1_v0.j2
│   └── relation_stage2_v0.j2
├── research/
│   ├── CITATION_AUDIT.md
│   ├── deep_research_report.md
│   ├── LITERATURE_POSITIONING.md
│   └── MASTER_EXECUTION_PROMPT.md
├── schema/
│   ├── generated/
│   │   ├── ask_memory.schema.json
│   │   └── schema.sql
│   └── ask_memory.yaml
├── scripts/
│   ├── analyze_longmemeval_failures.py
│   ├── audit_m4w13_sweep.py
│   ├── bench_inference.py
│   ├── build_failed_slice_from_run.py
│   ├── build_relation_dev100_from_research.py
│   ├── build_slice.py
│   ├── build_stratified_slice.py
│   ├── build_v8_adjudicated_report.py
│   ├── build_v8_topup_slice.py
│   ├── check_drift.py
│   ├── check_m4w16.py
│   ├── compare_relation_robustness.py
│   ├── compute_mgp6_agreement.py
│   ├── debug_controller_trace.py
│   ├── evaluate_rc_at_c_mgp6.py
│   ├── evaluate_recoverability_mgp6.py
│   ├── evaluate_smrr_mgp6.py
│   ├── finalize_m1w1.sh
│   ├── finalize_m1w2.sh
│   ├── finalize_m1w3.sh
│   ├── finalize_m1w4.sh
│   ├── m4w13_validation.py
│   ├── merge_v8_full180.py
│   ├── print_report.py
│   ├── promote_lme_to_final.py
│   ├── promote_to_final.py
│   ├── regrade.py
│   ├── rejudge.py
│   ├── replay_m4w13_failures.py
│   ├── run_baseline.py
│   ├── run_external_lme.py
│   ├── run_extraction.py
│   ├── run_m4w13_a10g_sweep.py
│   ├── run_m4w13_hf.py
│   ├── run_m4w13_hf_a100_parallel.py
│   ├── run_m4w13_ollama.py
│   ├── run_m4w15.py
│   ├── run_mgp6.py
│   ├── run_relation_classifier.py
│   ├── run_vllm_cascade.py
│   ├── serve_embeddings.py
│   ├── setup_venv.sh
│   ├── simulate_computation_answerer.py
│   ├── smoke_e2e.py
│   ├── smoke_extraction_pipeline.py
│   ├── summarize_m4w13.py
│   ├── validate_repository.py
│   ├── verify_homogeneous_run.py
│   └── win_loss.py
├── src/
│   ├── ask/
│   │   ├── audit/
│   │   │   ├── __init__.py
│   │   │   └── action_log.py
│   │   ├── baselines/
│   │   │   ├── prompts/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── embeddings.py
│   │   │   ├── flat_vector.py
│   │   │   ├── flat_vector_store.py
│   │   │   ├── naive_overwrite.py
│   │   │   ├── no_memory.py
│   │   │   └── recency_pruning.py
│   │   ├── classifier/
│   │   │   ├── __init__.py
│   │   │   ├── metrics.py
│   │   │   ├── relation.py
│   │   │   └── schema.py
│   │   ├── controller/
│   │   │   ├── __init__.py
│   │   │   ├── actions.py
│   │   │   ├── active.py
│   │   │   ├── computation.py
│   │   │   ├── features.py
│   │   │   ├── policy.py
│   │   │   ├── score.py
│   │   │   ├── scoring.py
│   │   │   └── temporal.py
│   │   ├── data/
│   │   │   ├── __init__.py
│   │   │   └── longmemeval.py
│   │   ├── eval/
│   │   │   ├── __init__.py
│   │   │   ├── computation_replay.py
│   │   │   ├── judge.py
│   │   │   ├── longmemeval.py
│   │   │   ├── m4w15.py
│   │   │   ├── m4w16.py
│   │   │   ├── merge.py
│   │   │   ├── mgp6.py
│   │   │   ├── mgp6_agreement.py
│   │   │   ├── mgp6_schema.py
│   │   │   ├── recoverability.py
│   │   │   ├── sanity.py
│   │   │   └── smrr.py
│   │   ├── extraction/
│   │   │   ├── __init__.py
│   │   │   ├── coverage.py
│   │   │   ├── extractor.py
│   │   │   └── schema.py
│   │   ├── inference/
│   │   │   ├── __init__.py
│   │   │   ├── fake.py
│   │   │   ├── fallback.py
│   │   │   ├── llm.py
│   │   │   ├── ollama.py
│   │   │   ├── openai_compatible.py
│   │   │   ├── openai_headers.py
│   │   │   ├── openmodel_messages.py
│   │   │   └── structured_pai.py
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── db.py
│   │   │   ├── models.py
│   │   │   └── operations.py
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   └── orchestrator.py
│   │   └── __init__.py
│   └── ask_memory_governance.egg-info/
│       ├── dependency_links.txt
│       ├── PKG-INFO
│       ├── requires.txt
│       ├── SOURCES.txt
│       └── top_level.txt
├── tests/
│   ├── fixtures/
│   │   └── m4w14_extraction_first_pass.jsonl
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_action_log.py
│   ├── test_actions.py
│   ├── test_active_config.py
│   ├── test_build_relation_dev100_from_research.py
│   ├── test_cascade_escalation.py
│   ├── test_classifier_schema_normalization.py
│   ├── test_computation_replay.py
│   ├── test_controller.py
│   ├── test_coverage_monitor.py
│   ├── test_e2e_smoke.py
│   ├── test_embeddings.py
│   ├── test_extraction_concurrency.py
│   ├── test_extraction_conf0_kept.py
│   ├── test_extraction_repair_regression.py
│   ├── test_extraction_schema.py
│   ├── test_extractor_recovery.py
│   ├── test_failed_slice_builder.py
│   ├── test_failure_analysis.py
│   ├── test_flat_vector.py
│   ├── test_flat_vector_store.py
│   ├── test_import_contracts.py
│   ├── test_judge_backend.py
│   ├── test_llm.py
│   ├── test_longmemeval.py
│   ├── test_longmemeval_eval.py
│   ├── test_m4w13_a10g_sweep.py
│   ├── test_m4w13_hf_runner.py
│   ├── test_m4w13_improvements.py
│   ├── test_m4w13_ollama_runner.py
│   ├── test_m4w13_validation.py
│   ├── test_m4w15.py
│   ├── test_m4w16.py
│   ├── test_memory_operations.py
│   ├── test_merge_shards.py
│   ├── test_mgp6_advisor_subsample.py
│   ├── test_mgp6_eval.py
│   ├── test_mgp6_schema.py
│   ├── test_mgp6_v2_scorer_regression.py
│   ├── test_naive_overwrite.py
│   ├── test_nextgen_thinking_embedder.py
│   ├── test_no_memory.py
│   ├── test_ollama.py
│   ├── test_openai_compatible.py
│   ├── test_openai_headers.py
│   ├── test_openmodel_messages.py
│   ├── test_pipeline_orchestrator.py
│   ├── test_prompt_budget.py
│   ├── test_quality_preset_flag_override.py
│   ├── test_recency_pruning.py
│   ├── test_recoverability.py
│   ├── test_rejudge.py
│   ├── test_relation_classifier.py
│   ├── test_relation_metrics.py
│   ├── test_run_baseline_resume.py
│   ├── test_run_relation_classifier.py
│   ├── test_run_sanity.py
│   ├── test_run_vllm_cascade_logging.py
│   ├── test_scaleup_500_m_fixes.py
│   ├── test_schema.py
│   ├── test_scoring.py
│   ├── test_smrr.py
│   ├── test_supersede.py
│   ├── test_temporal.py
│   ├── test_thesis_profile_tier_guard.py
│   └── test_v4_run_fixes.py
├── thesis/
│   ├── MASTERS_THESIS_ASK_MGP6.md
│   ├── README.md
│   └── references.bib
├── .env.example
├── .gitattributes
├── .gitignore
├── BLOCKERS.md
├── CHANGELOG.md
├── CITATION.cff
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── DECISION_LOG.md
├── EVIDENCE_REGISTRY.yaml
├── EXPERIMENT_REGISTRY.yaml
├── GIT_PUSH_GUIDE.md
├── INIT_GIT.sh
├── LICENSE
├── LICENSE-DATA.md
├── Makefile
├── PROJECT_STATE.md
├── pyproject.toml
├── README.md
├── SECURITY.md
└── WORKPLAN.md
```
