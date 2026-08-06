# Validation report

Validated on 2026-07-15 in the local release environment.

## Repository and code

| Gate | Result |
|---|---|
| Ruff | pass, `ruff check .` |
| Mypy | pass, 60 source files |
| Pytest | pass, 472 passed, 11 documented optional skips |
| MGP-6 strict schema | pass, 180 examples, 0 errors |
| Offline smoke suite | pass, tests, strict schema, two-item dry run |
| Repository secret/structure scan | pass |
| Build | pass, sdist and universal wheel |
| Isolated wheel install/import/resources | pass, wheel installed with `--no-deps`; package import and four required resources verified |

The optional skips are nine computations requiring a non-redistributed
LongMemEval fixture and two MiniLM smoke tests disabled by the documented
Apple-Silicon `libomp` safety gate.

## Research artifacts

| Artifact | Result |
|---|---|
| Ledger | canonical v1.1; exact status vocabulary enforced |
| MGP-6 data | 180 rows; no schema errors; shortcut gate failed (conflict type reaches 1.000 held-out accuracy) |
| MGP-6 validity audit | pass, cluster intervals, finite-sample bounds, calibration, risk–coverage, and cost sensitivity regenerated |
| Freeze manifest | regenerated from exact bytes plus external input hashes |
| Paper | 16 pages; all pages visually inspected; no overfull boxes or unresolved citations/references |
| Thesis | 42 tagged pages; all pages inspected across the final review cycle; accessibility 0/0/0; 46 cited keys resolve against 49 entries |
| Defense decks | 31 slides each; automated overflow pass; every Persian slide and all English layouts visually inspected |
| Defense PDFs | 31 tagged pages each; unencrypted; no PDF suspects; rendered QA passed |
| Cambridge documents | 24 rendered pages across four pairs; accessibility 0 issues |

## Release sanitization

The canonical public repository excludes `.git`, virtual environments, local
runs, LongMemEval data, logs, model answer/judgment files, private Cambridge
materials, compiled personal documents, absolute machine paths, secrets, raw
independent-human labels pending consent, and per-item model-annotation
rationales. Aggregate statistics and the two withheld human-source SHA-256
hashes remain.

A provisional archive and, after the final prose freeze, the definitive outer
archive and nested public-repository ZIP were extracted into clean temporary
directories. On the definitive bytes, every `SHA256SUMS` entry and the separate
`OUTER_ZIP.sha256` check passed; both ZIP integrity tests passed. The extracted
public copy passed the repository validator, 472-test offline suite, strict
180/0 MGP-6 validation, and two-item dry run. It also built an sdist and
universal wheel; a fresh virtual environment installed that wheel without
dependency resolution, imported `ask`, and found all four required packaged
configuration/schema resources. The nested ZIP independently passed the
repository, bibliography, strict-schema, test, and build checks.
