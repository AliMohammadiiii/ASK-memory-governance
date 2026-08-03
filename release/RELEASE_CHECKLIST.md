# Release checklist

Status: `NO_GO`

- [ ] Freeze a clean Git commit and record the commit/tree hashes.
- [ ] Pass full offline tests, claim verification, trace validation, manifest
  verification, clean reproduction, and paper build.
- [ ] Resolve every `BLOCKED_HUMAN_LEGAL_DECISION` in the license matrix.
- [ ] Include only files allowed by `PUBLIC_PRIVATE_MATRIX.csv`.
- [ ] Scan for secrets, local paths, hidden labels, personal data, author
  identity, PDF metadata, and forbidden raw annotations.
- [ ] Build from tracked files only; hash every release file.
- [ ] Independently inspect the built archive, not only the source tree.
- [ ] Freeze authorship, venue declarations, artifact DOI/URL, and citation.
- [ ] Re-run `scripts/check_readiness.py`; release only on the intended GO state.

