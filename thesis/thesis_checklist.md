# Thesis Review and Submission Checklist

This checklist separates repository-complete review work from University of Tehran requirements that remain external.

## A. Evidence freeze

- [x] Master draft references ledger v1.1.
- [x] Ledger SHA-256 recorded in the draft and number audit.
- [x] Eligibility vocabulary is canonical: `final_candidate`, `diagnostic_only`, `failure_replay_only`, `incomplete`, `invalid`, `externally_pending`.
- [x] Few-shot row disclosed as 174/180 and coverage-aware 0.7833/0.7692.
- [x] Failure replay excluded from result claims.
- [x] Modal top-up counts and 53.3%–67.8% raw bounds included.
- [x] SSP v7/replay/top-up evidence kept configuration-specific.
- [x] final-1.1 disclosed as externally pending after HTTP 403 before inference.
- [ ] Recompute the ledger hash and recompile if `artifacts/results_ledger.json` changes.

## B. Claims and scholarship

- [x] MGP-6 described as an author-designed diagnostic slice.
- [x] Rule-vs-LLM null stated correctly (Holm p=0.286).
- [x] External adapter mappings disclosed.
- [x] Annotation phrased as one independent annotator plus a four-model panel.
- [x] Novelty narrowed to operationalization and layered evaluation.
- [x] No primacy claim for update/versioning/provenance/lineage/abstention/gating.
- [x] Every Markdown citation key has a BibTeX entry.
- [ ] Human bibliography audit: titles, complete author lists, venues, years, DOIs/URLs.
- [ ] Apply the citation style required by the University of Tehran template.

## C. Administrative fields, external

- [ ] Obtain the current official University of Tehran thesis template and regulations.
- [ ] Candidate full legal name (English and Persian).
- [ ] Student number.
- [ ] Degree, programme, department, faculty, and campus wording.
- [ ] Supervisor, advisor, and examiner names/titles with approvals.
- [ ] Submission, approval, and defense dates.
- [ ] Signatures, seals, and committee pages.
- [ ] Acknowledgements and dedication approved by the candidate.
- [ ] Ethics/approval statement confirmed with the department.

## D. Institutional layout, external

- [ ] Transfer the English review draft into the official template.
- [ ] Confirm paper size, margins, fonts, binding gutter, and section order.
- [ ] Confirm Persian abstract and extended-summary requirements.
- [ ] Confirm bilingual title-page wording.
- [ ] Generate and update the table of contents and lists of figures/tables.
- [ ] Verify Roman/Arabic page-number transitions and section breaks.
- [ ] Check equation, table, figure, appendix, and citation numbering in Word.
- [ ] Confirm PDF/A or archival-export requirements.

## E. Final technical QA

- [x] Editable English review-draft DOCX generated.
- [x] Review-draft PDF generated from the DOCX.
- [x] DOCX accessibility audit run.
- [x] Heading hierarchy and table structure checked.
- [x] Every rendered DOCX/PDF page visually inspected for clipping, overlap, broken tables, and missing glyphs.
- [ ] Re-run all QA after applying the official institutional template.
- [ ] Open the final DOCX in Microsoft Word and update all fields.
- [ ] Verify every hyperlink and cross-reference.
- [ ] Verify final page count and print output.

## F. Open research cells

- [ ] Execute the independent MGP-6 v3 protocol with controller/data-author separation.
- [ ] Obtain three blinded human annotations and independent adjudication.
- [ ] Run the frozen shortcut gates before unblinding policy predictions.
- [ ] Complete component-oracle, native external-system, and multi-step trajectory runs.
- [ ] Execute a homogeneous downstream run only after all provenance gates pass.

The unchecked cells keep MGP-6 v2 diagnostic and prohibit external-generalization, population-safety, native-system-ranking, or downstream-improvement claims.
