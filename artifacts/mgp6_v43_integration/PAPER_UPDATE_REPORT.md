# MGP-6 v4.3 paper update report

Updated the real LaTeX sources, not the untracked `paper.md` representation:

- `sections/04_mgp6.tex`: v4.3 identity, 900/100-component construction,
  split strategy, shortcut remediation, human validation, attestation limit,
  and public model-field boundary.
- `sections/06_experimental_setup.tex`: staged public/dev/freeze/hidden protocol.
- `sections/07_results.tex`: explicit v4.3 final-hidden placeholders only.
- `sections/09_discussion_limitations.tex`: controlled-diagnostic scope,
  licensing, and private-data limitations.
- `appendix.tex`: release material and reproducibility boundary.

Historical v2 text remains in place, while LongMemEval remains separate external
evaluation. No v4.3 performance number was inserted. Existing tracked build
outputs were inspected and left unchanged. A temporary-directory `latexmk`
build completed successfully; no generated paper output was replaced.
