# MGP-Natural implementation plan

## Completion standard

The repository is complete for this execution only when all machine-actionable checks pass, every generated report is internally consistent, and all human-only gates remain explicitly blocked rather than inferred as approved.

## Phases

1. Evidence inventory and StudyChat scope classification.
2. Source and venue evidence audit.
3. Typed ingestion, reconstruction, mining, privacy, blinding, annotation, adjudication, continuity, splitting, scoring, trajectory, claim, readiness, and release modules.
4. Synthetic fixtures plus private execution against the supplied derivative.
5. Iterative test, lint, type, build, package-boundary, and clean-room reproduction checks.
6. Final readiness, security, packaging-boundary, execution-summary, and blocker reports.

## Machine-verifiable completion criteria

- Input hashes and record counts are reproducible.
- Supplied StudyChat material is classified from content, not filename.
- Every CLI supports `--help` and fails closed.
- Schemas reject leakage and invalid state semantics.
- Private packet generation uses HMAC IDs, restrictive permissions, allowlisting, and a mapping commitment.
- Split construction assigns connected components, not records.
- Scoring rejects provisional or incomplete gold unless explicit smoke mode is used.
- Public packaging remains blocked while human gates are unresolved.
- Unit and integration tests, supplementary static checks, exact private-mode checks, wheel/sdist build, public-boundary validation, and clean-room validation pass. Named Ruff, mypy, Python 3.11/3.12, and external scanner results are required when those tools are available; absence is an explicit environment blocker, never an inferred pass.

## Execution outcome (2026-08-04)

- Completed all locally executable pipeline and fixture-validation phases.
- Preserved a `NO_GO` verdict because full StudyChat coverage, natural WikiConv acquisition, valid held-out splits, independent gold, and human approvals are absent.
- Repaired inherited private directory modes and added a deterministic exact-mode audit.
- Added consolidated execution, security, package-boundary, and acquisition-blocker reports.
- Did not publish, upload, accept gated terms, collect annotations, reveal mappings, call paid APIs, or create a DOI.

