# Project state

Updated: 2026-07-26.

## Repository status

The maintained package, tests, benchmark contracts, release tooling, and
documentation are organized for an offline source release. Generated handoff
bundles and local experiment outputs are excluded from the repository boundary.

## Validation contract

`make check` is the fast offline development gate. `make release-check` is the
complete offline source-release gate and is mirrored by CI on Python 3.11 and
3.12. Exact results belong in dated validation reports; this page intentionally
does not freeze a test count that will become stale after the next regression
test.

## Scientific status

- MGP-6 v2 remains an author-designed diagnostic; its construct-validity gate
  failed because conflict type alone predicts the held-out gold action.
- MGP-6 v3 independent confirmation is designed but not yet executed.
- A homogeneous final LongMemEval result remains externally pending.
- Historical failure replays, incomplete runs, and heterogeneous judge
  constructions are not promoted to final capability results.

The authoritative interpretation is
`docs/audit/SCIENTIFIC_SOURCE_OF_TRUTH.md`.

## External blockers

- authorized hosted-model access and non-redistributed LongMemEval input;
- independent writers, annotators, and adjudication for MGP-6 v3;
- official venue and University of Tehran templates and administrative facts;
- real public repository metadata and redistribution consent where required.
