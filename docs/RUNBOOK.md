# Maintainer runbook

1. Use Python 3.11 or 3.12 and install `.[dev]`.
2. Run `make check PYTHON=.venv/bin/python`.
3. Regenerate inventory, derived manifest, claims, and readiness in that order.
4. Inspect `claims/mismatch_report.json`; unexplained mismatches must be zero.
5. Run trace, public-data, release, anonymity, and paper checks against the
   frozen candidate archive.
6. Resolve human/legal/authorship/independent-annotation gates with signed
   records; never encode an inferred approval.
7. Rebuild and hash the final archive from a clean, tagged commit.
8. Submit only if readiness is exactly the intended GO state.

Historical artifacts and manifests are immutable. Paid inference, external
data acquisition, publication, and external writes require separate authority.

