# Publication GO / NO-GO

Final status: **NO_GO**

## Blocking gates

| Venue | Gate | Authority | Resolution evidence |
|---|---|---|---|
| TMLR | `licenses_and_redistribution_resolved` | `human_legal` | `reports/LICENSE_BLOCKERS.json` |
| TMLR | `new_confirmation_protocol_completed` | `independent_human_and_machine` | `confirmation/reports/` |
| TMLR | `independent_annotation_satisfied` | `independent_human` | `confirmation/adjudication/` |
| TMLR | `authorship_and_openreview_resolved` | `human` | `publication/OPENREVIEW_PROFILE_CHECKLIST.md` |
| TMLR | `current_venue_constraints_checked` | `machine_and_human` | `publication/VENUE_REQUIREMENTS_SNAPSHOT.md` |
| JMLR | `natural_write_labelled_evidence_completed` | `independent_human_and_machine` | `confirmation/natural_challenge/` |
| JMLR | `independent_annotation_completed` | `independent_human` | `confirmation/adjudication/` |
| JMLR | `trajectory_propagation_and_recovery_evaluated` | `machine` | `confirmation/reports/trajectory.json` |
| JMLR | `model_family_breadth_satisfied` | `paid_or_external_execution` | `experiments/model_matrix.yaml` |
| JMLR | `cross_storage_or_native_system_evidence_completed` | `external_execution` | `reports/native_systems.json` |
| JMLR | `multi_judge_or_human_validation_completed` | `independent_human_or_external_execution` | `reports/judge_robustness.json` |
| JMLR | `robustness_analysis_completed` | `machine_and_external_execution` | `reports/robustness.json` |
| JMLR | `generalizable_ml_lessons_demonstrated` | `scientific_review` | `docs/JMLR_READINESS.md` |
| JMLR | `jmlr_compliance_satisfied` | `machine_and_human` | `publication/VENUE_REQUIREMENTS_SNAPSHOT.md` |

A template or empty directory does not satisfy a gate. Human gates require an explicit
recorded decision or independent contribution. Machine gates require a successful
validation artifact from the authoritative command.
