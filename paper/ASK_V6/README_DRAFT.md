# ASK arXiv draft, revision 4 (2026-10-02)

Status: bounded draft under rewrite gate OPEN (decision D21). Not compiled in the audit sandbox (no working TeX compiler there). Static checks passed: every cited key is in references.bib, every reference has a label, environments and braces balance, no em or en dashes, no benchmark text, no banned priority words.

## Compile
```
pdflatex main && bibtex main && pdflatex main && pdflatex main
```
Needed packages: booktabs, array, tabularx, graphicx, enumitem, natbib, hyperref, microtype, amsmath. Tables use tabularx at the text width. After compiling, check the log for `Overfull \hbox` and for undefined references; paste the log lines if any remain.

## Files
main.tex, author_info.tex (add affiliation and contact here), sections/00 to 08, references.bib (35 entries), figures/fig_models, figures/fig_lme, tables/*.tex. `make_multimodel_assets.py` and `make_fig_lme.py` regenerate the figures and tables from `ASK_supplement/substitute_runs/analysis/phase16_cluster_analysis.json`.

## Supplement (ASK_supplement.zip)
ARTIFACT_MANIFEST.csv maps every file to the claim and section it supports (SHA-256 per file). Contents: related-work search log and claim trace (SEARCH_LOG.csv must ship because Section 2 says the search record is released), substitute-run rows and analyses, parser provenance (patch and hashes), validator patch and tests, V12 run reconciliation (883 rows, coverage, evaluated-code manifest and diffs, overrides, adjudication record), claim-check reports.

## Owner actions before submission
1. Affiliation and contact in author_info.tex.
2. Compile and check the log (overfull boxes, undefined references).
3. Decide on the two patches: the parser change (parser_provenance/parser_fence_normalization.patch) and the validator patch (validator/validator_fix.patch). The audit did not modify the repository.
4. Run ARCHIVE_COMMANDS_FOR_OWNER.sh (in v12_run/) or an equivalent to preserve the ten unreferenced evaluated-code blobs.
5. Optional runs with the kit in p17_user_kit: clean factorial diagnostic, hidden structural audit, fresh matched LongMemEval run (needs paid execution and a pre-registered protocol).
6. Questions only the owner can answer: who made the three baseline overrides and the nine adjudications and on what criteria; whether annotators were independent of the authors; how invocation 3 of the V12 run ended.
7. Human peer review.

## Claim checks
Check 1 (revision 0): 171 statements, 7 contradicted. Check 2 (revision 1): 177 statements, 3 contradicted, 30 weaker, 7 unverifiable. Check 3 (revision 3): 268 rows, 203 supported, 28 weaker, 2 contradicted, 35 unverifiable (26 are Section 2 sentences about other works); all applied in revision 4. The Discussion contains a paragraph disclosing AI assistance; edit or remove it as you decide.
