# Scientific integrity check

## Result

PASS for locally verifiable integrity properties. No new empirical, legal,
human-annotation, or provider-execution claim was created.

## Evidence checks

- Claim verification: 26 claims, zero mismatches.
- LongMemEval derived manifest: parent hashes and declared anomalies match.
- Public/private boundary: declaration passes; legal clearance remains false.
- Paper fragments: 5 generated files and 18 required fragments match their
  machine-readable evidence.
- Prompt identity: all 9 prompt templates are registered and their SHA-256
  hashes match.
- Recorded-evidence formatting: generic whitespace hooks exclude annotation
  CSVs, prompt bytes, claim records, experiment records, generated tables, and
  figure evidence. An initial hook normalization was reversed byte-for-byte.
- Historical moves: 13 archived files retain identical hashes. Four maintained
  documents were moved and deliberately rewritten; old and new hashes are in
  `MIGRATION_MAP.csv`.
- Duplicate review: four exact tracked duplicate roles remain because removing
  them would weaken typing, packaging, manuscript, or experiment provenance.
- Hidden/private execution: no hidden split was rescored, no private input was
  exposed, no paid provider call was made, and no independent review was
  fabricated.

## Manuscript checks

The paper compiles to 44 pages. The thesis compiles to 157 pages after repairing
the pre-existing malformed table row. The completed bibliography pass reports
no undefined citations or references. Unknown administrative values remain
absent from the title-page content and are listed in
`thesis/frontmatter/ADMINISTRATIVE_FIELDS.md`.

## Interpretation boundary

The offline engineering and integrity gates pass. The publication readiness
engine correctly remains `NO_GO` because 16 external or human-controlled gates
are open. This result is not a publication, safety, legal, independent-audit,
or external-validity approval.
