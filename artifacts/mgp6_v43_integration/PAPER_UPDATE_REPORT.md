# MGP-6 v4.3 paper update report

Updated the real LaTeX sources, not the untracked `paper.md` representation:

- `sections/04_mgp6.tex`: v4.3 identity, 900/100-component construction,
  split strategy, shortcut remediation, human validation, attestation limit,
  and public model-field boundary.
- `sections/06_experimental_setup.tex`: staged public/dev/freeze/hidden protocol
  plus the completed prediction-seal and resume provenance.
- `sections/07_results.tex`: the single final hidden configuration's aggregate
  accuracy, macro-F1, per-class metrics, confusion matrix, component-cluster
  intervals, coverage, abstention/selective metrics, and operational limits.
- `sections/09_discussion_limitations.tex`: controlled-diagnostic scope,
  licensing, and private-data limitations.
- `appendix.tex`: release material and reproducibility boundary.

Historical v2 text remains in place, while LongMemEval remains separate external
evaluation. The v4.3 result is explicitly one frozen controlled-synthetic
configuration, not a final baseline comparison or generalization claim.
Existing tracked build outputs were inspected and left unchanged. A
temporary-directory `latexmk` build completed successfully without replacing
generated paper output.
