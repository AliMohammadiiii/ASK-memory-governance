# Master execution status

Updated: 2026-07-26. Statuses: not_started | in_progress | implemented | validated | externally_pending | blocked | invalidated | complete.

| # | Workstream | Status | Evidence / gate |
|---|---|---|---|
| A1 | Input inventory and availability | complete | `docs/REPOSITORY_INVENTORY.md`; dated predecessor archived under `docs/history/` |
| A2 | Metric recomputation & run classification | complete | `artifacts/results_ledger.json`, `artifacts/controller_run_comparison.json`, `docs/audit/ARTIFACT_TRUTH_TABLE.csv`; MGP-6 rows recomputed from aligned 180-item files; historical 139/180 classified as selection-biased `failure_replay_only`, not a result |
| A3 | Leakage / degrees-of-freedom audit | complete | `docs/audit/DATA_LEAKAGE_AND_RESEARCHER_DEGREES_OF_FREEDOM.md` |
| A4 | MGP-6 construct-validity audit | validated | `scripts/analysis/audit_mgp6_validity.py` and `artifacts/analysis/mgp6_validity_audit.{json,md}`; conflict-type-only lookup reaches 1.000 test accuracy, so v2 remains diagnostic |
| B1 | Canonical repository base | validated | Repository structure, release exclusions, configuration, packaging metadata, and runtime resources validated |
| B2 | Repo re-validation in current environment | validated | The maintained offline gate is `make check`; the full source-release gate is `make release-check`. Exact dated counts stay in validation reports rather than this status ledger |
| C1 | ControllerRun reconstruction | complete | `docs/audit/CONTROLLERRUN_RECONSTRUCTION.md`, `CONTROLLERRUN_FAILURE_LEDGER.md`, `BEHAVIOR_TO_CODE_TRACEABILITY.md` |
| C2 | Single-session preference analysis | complete | 19-item taxonomy; v7 diagnostic 11/30; selected replay 0/19 but non-comparable prompts/contexts; top-up 8/29 with one unresolved (maximum 9/30). Proposed seven-arm correction experiment remains unexecuted and cannot support a claim |
| D1 | Recorded final evaluation protocol | complete | `FINAL_EVALUATION_PROTOCOL.md`, `FINAL_RUN_MATRIX.yaml`, `FINAL_METRIC_DEFINITIONS.md`, `FINAL_ANALYSIS_PLAN.md`, `configs/release/final.yaml`; commitment hashes regenerated from final bytes |
| D2 | Homogeneous LongMemEval final-1.1 run | externally_pending | all supplied-key probes returned HTTP 403 before inference; no prediction entered the ledger; exact smoke/full/resume/verifier commands in `reports/REMAINING_EXTERNAL_ACTIONS.md` |
| D3 | MGP-6 six-shot baseline recomputation | complete | 174 observed predictions plus six coverage-aligned `INVALID` rows yield 0.7833 accuracy / 0.7692 macro-F1; row remains `incomplete` and is excluded from headline comparisons |
| D4 | Independent MGP-6 v3 confirmation | not_started | prospective protocol recorded in `benchmarks/mgp6/MGP6_V3_INDEPENDENT_PROTOCOL.md`; independent writers, three-human annotation, hidden test execution, and model runs require external work and are not fabricated |
| E1 | Reports & adversarial review | complete | Final results, statistics, threats, claim matrices, error analysis, Reviewer 2 audit, and handoff reports aligned to ledger v1.1 |
| F1 | Related work / novelty / venue strategy | complete | `reports/RELATED_WORK_UPDATE.md`, `NOVELTY_MATRIX.csv`, `paper/PUBLICATION_STRATEGY.md`; no venue template fabricated |
| G1 | Diagnostic paper rewrite | validated | anonymous 16-page paper leads with shortcut leakage and held-out null/trade-off results; mapped external systems and contaminated/incomplete downstream evidence are excluded from the main text; LaTeX compile and full visual QA pass |
| G2 | Separate Paper 2 gate | complete | distinctness gate not met; a second paper was deliberately not manufactured; rationale in `paper/PUBLICATION_STRATEGY.md` |
| H1 | Thesis review package | validated | 42-page tagged DOCX/PDF, accessibility 0/0/0, full visual QA, English source, Persian companion, number audit, summaries, checklist, and 60 defense Q&As; official university formatting remains a user gate |
| I1 | Laptop scripts & return-package spec | complete | deterministic smoke/full/resume wrappers, homogeneous-run verifier, judge audit, review packager, and exact commands documented |
| J1 | Final ZIP with extracted-copy validation | validated | 2026-07-15 outer/nested ZIP integrity and checksums pass; extracted public copy passes repository, bibliography, 472-test, strict-schema, build, and isolated wheel import/resource gates |

## Hard blockers (user-only inputs)

1. **Authorized hosted-model access**, credential rotation/authorization is an account-owner action; it blocks D2 and any hosted correction/judge audit. LongMemEval inputs remain external and are not redistributed.
2. **University of Tehran thesis template and administrative facts**, advisor, department, student number, approvals, and required Persian typography/order.
3. **Cambridge application facts and permissions**, entry cycle, supervisor permission/capacity, records, evidence, referees, and final submission documents.
4. **Publication choices/permissions**, actual venue and current template, real Git remote, and written consent before redistributing raw independent-human labels.
5. **Independent confirmation labor**, v3 requires data writers separated from controller design, three blinded human annotators, adjudication, and completed precommitted model runs.
