# Venue requirements snapshot

Checked: 2026-08-02 (Asia/Tehran). This is an operational snapshot, not legal
advice. A human author must re-check every linked page immediately before
submission.

## TMLR

Official sources: [author guide](https://jmlr.org/tmlr/author-guide.html),
[submission instructions](https://jmlr.org/tmlr/submissions.html), and
[editorial policies](https://jmlr.org/tmlr/editorial-policies.html).

- Rolling submission through OpenReview; double-blind review.
- Manuscript and supplementary material must be anonymized and use the official
  TMLR LaTeX template without layout-changing modifications.
- Every author needs a complete, active OpenReview profile, including
  affiliations, conflicts, and publication history.
- Submission metadata must address action-editor suitability, human-subjects
  reporting, funding, competing interests, and uncovered conflicts.
- Supplementary material may be PDF or ZIP, up to 100 MB, and must be
  anonymized. Reproducibility material is encouraged.
- The submission is CC BY 4.0 from submission through publication; authors
  retain copyright.
- Simultaneous/overlapping archival submission and reuse of text, figures, or
  results from archival work are restricted by the editorial policies.

Repository state: machine snapshot complete; author/OpenReview, licensing,
anonymity, ethics, and conflict declarations remain unsigned. **Gate: BLOCKED.**

## JMLR

Official sources: [information for authors](https://www.jmlr.org/author-info.html),
[format instructions](https://jmlr.org/format/format.html), and
[final-preparation guide](https://jmlr.org/format/authors-guide.html).

- JMLR accepts work in ML theory/methods and expects broad ML interest,
  articulated claims, sound empirical or theoretical support, and reproducible
  experiments where appropriate.
- Simultaneous submission to another journal or conference is prohibited.
- Prior workshop/conference versions must be disclosed and substantively
  extended; overlapping prior work and the delta must be described.
- Initial submission must use the official JMLR LaTeX style. The abstract is at
  most 200 words, five keywords are required, and the upload is under 5 MB.
- A cover letter must record overlapping work, all-author consent, conflicts,
  3--5 suitable Action Editors, 3--5 suitable reviewers, and keywords.
- Manuscripts above 35 pages may be harder to review; above 50 pages require a
  cover-letter justification and may be desk rejected.
- Funding and conflicts must be disclosed. Accepted papers use a CC BY license;
  copyright remains with the authors and no publication fee is charged.

Repository state: the current evidence does not yet establish the breadth,
independent validation, robustness, and clean release expected for a defensible
JMLR submission. **Gate: BLOCKED.**

## Routing decision

The repository readiness engine is authoritative. Submit to neither venue while
`reports/readiness.json` says `NO_GO`. If all TMLR gates pass but any JMLR-only
gate fails, use TMLR. Choose JMLR only if every gate passes and the final paper
states general ML lessons rather than presenting a narrow application artifact.

Human re-check: `BLOCKED_HUMAN_DECISION`

