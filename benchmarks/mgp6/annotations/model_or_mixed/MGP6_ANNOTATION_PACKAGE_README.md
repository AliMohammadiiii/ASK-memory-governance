# MGP-6 Annotation Complete Package

This package contains the files generated and used during the annotation and agreement-analysis workflow.

## Primary human annotation outputs
- `human_independent_annotations_test.csv` — the 90-item independent human annotation.
- `human_annotation_agreement_report.md` — human-vs-author agreement report.
- `human_annotation_agreement_summary.json` — machine-readable human agreement metrics.
- `human_vs_author_disagreements.csv` — disagreement cases requiring adjudication.

## Blind annotation material
- `mgp6_v2_test_blind_annotation.jsonl` — test-only blinded annotation input with only the fields needed for annotation.

## Multi-model audit
- `geminiPro.csv`
- `gptSolHigh.csv`
- `kimi.csv`
- `z.csv`
- `mgp6_annotation_agreement_report.md`
- `mgp6_annotation_agreement_summary.json`
- `mgp6_annotator_metrics.csv`
- `mgp6_pairwise_agreement.csv`
- `mgp6_per_type_agreement.csv`
- `mgp6_per_class_metrics.csv`
- `mgp6_confusion_matrices_long.csv`
- `mgp6_disagreements_for_adjudication.csv`
- `mgp6_consensus_all_test.csv`
- `mgp6_annotation_agreement_outputs.zip`

## Additional files
- `independent_annotations_test.csv` — earlier model-produced annotation file.
- `mgp6_v2(1).jsonl` — source/gold dataset used for comparison.

## Key human agreement result
- Test items: 90
- Raw agreement with author gold: 98.89%
- Cohen's kappa: 0.9815
- 95% bootstrap CI for kappa: [0.9400, 1.0000]
- Macro-F1: 0.9913
- Disagreements: 1

Important: the four model annotation files are a secondary multi-model audit. The primary Phase 2 independent annotation is the human annotation file.
