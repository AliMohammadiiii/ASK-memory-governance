# Release checklist

- [x] Remove placeholder repository URLs; add real URLs only after a public host exists.
- [ ] Obtain a newly authorized API credential (the supplied key returned HTTP 403).
- [ ] Run `make repo-check`.
- [ ] Run `make test`, `make lint`, `make typecheck`, and `make build`.
- [x] License author-created MGP-6 material under CC BY 4.0.
- [ ] Obtain written consent before adding the independent annotator's raw labels
      to a public release; until then the public bundle excludes the two raw CSVs.
- [ ] Verify no LongMemEval or private conversation data is committed.
- [ ] Freeze code, data, prompt, and config hashes for confirmation runs.
- [ ] Generate tables from machine-readable reports.
- [ ] Select official paper and University of Tehran thesis templates.
