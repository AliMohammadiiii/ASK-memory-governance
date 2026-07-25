# Thesis workspace

This directory contains an **English review draft**, not an institution-ready submission. The scientific source of truth is the 2026-07-15 construct-validity audit in `artifacts/analysis/mgp6_validity_audit.json`, with the v1.1 ledger retained for historical run provenance.

## Deliverables

- `MASTERS_THESIS_ASK_MGP6.md` — complete English master draft.
- `two_page_summary.md` — compact research summary.
- `contribution_summary.md` — defensible contribution and non-claim boundary.
- `defense_questions.md` — oral-defense preparation.
- `claims_evidence_matrix.md` — thesis-scoped claim gate.
- `THESIS_NUMBER_AUDIT.md` — ledger v1.1 number audit.
- `frontmatter/` — Persian abstract/summary/terminology and administrative placeholders.
- `references.bib` and `references/README.md` — consolidated bibliography and audit notes.
- `compiled/ASK_Masters_Thesis_English_Review_Draft.docx` — editable review copy.
- `compiled/ASK_Masters_Thesis_English_Review_Draft.pdf` — rendered review copy.

## Evidence status

MGP-6 v2 policy results are diagnostic: conflict type alone reaches 1.000 held-out accuracy, so the pilot does not isolate evidence reasoning. The reference policy obtains 0.8889 test accuracy versus 0.9000 for the structured LLM, with a family-clustered paired interval containing zero. The few-shot result is incomplete; mapped external-system rankings and all LongMemEval evidence are non-primary.

## External completion requirements

The repository does not contain the official University of Tehran thesis template or verified administrative metadata. Before institutional submission, a human must:

1. obtain and apply the current official template and regulations;
2. fill candidate, student number, department/faculty, supervisor/advisor, approval, defense, and signature fields;
3. confirm Persian-front-matter requirements and typography with the department;
4. choose and validate the required citation/bibliography style;
5. update Word fields, table of contents, lists of figures/tables, and page numbering in the official template;
6. rerun the ledger/hash, citation, structural, accessibility, and visual QA checks; and
7. execute or continue to disclose the independent v3 confirmation and any externally pending downstream protocol.

Use `thesis_checklist.md` as the handoff gate. Do not treat the review DOCX/PDF as an official submission artifact.
