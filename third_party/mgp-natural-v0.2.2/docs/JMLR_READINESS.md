# JMLR Readiness Standard

## Relationship to TMLR readiness

A high-quality dataset and TMLR-style benchmark evaluation are necessary but not sufficient for a stronger JMLR submission. JMLR readiness requires broader scientific evidence and generalizable conclusions about write-time memory governance.

## Additional evidence

- larger independently adjudicated natural gold in both tracks;
- multiple model families and memory-controller architectures;
- multiple judge or human-validation pathways;
- native memory-system or cross-storage evaluation;
- real chronological trajectories with propagation and recovery analysis;
- robustness and guideline-sensitivity studies;
- calibration and selective-risk analysis;
- statistical power and cluster-aware comparisons;
- downstream consequences of incorrect state transitions;
- a detailed error taxonomy; and
- generalizable lessons that extend beyond source-specific heuristics.

## Trajectory standard

A real trajectory study must measure first incorrect write, downstream corruption, stale-state persistence, recovery after correction, repeated abstention, improper overwrite, lineage breakage, evidence loss, and final-state exactness. Synthetic trajectory tests validate code only.

## Robustness standard

Label-preserving and decision-changing perturbations must be separated prospectively. Hidden-test perturbations cannot guide model tuning. Results should cover paraphrase, truncation, distractors, conflict, order, anonymization, long distance, domain shift, slot names, ambiguity, calibration, and annotation-guideline sensitivity.

## Native-system evidence

At least one study should apply predicted decisions in an actual memory system or multiple storage/controller designs. It should trace writes, state versions, retrieval, downstream use, and recovery, rather than scoring only isolated labels.

## Current status

`jmlr_ready = false`. No additional JMLR evidence gate is complete: there is no sufficient natural gold, real trajectory evaluation, multi-family model comparison, independent judge pathway, robustness study, native memory-system evidence, calibration study on natural gold, generalizable ML finding, or scientific-breadth approval. The repository supplies interfaces, schemas, synthetic tests, and a roadmap only. JMLR readiness must not be claimed.

