# Decision log

## 2026-07-12 — Canonical source

Use `ASKCodes.zip` as the implementation base because it contains the complete package, scripts, and tests. The earlier generated `02_canonical_repository` was only a small evaluator and is retained conceptually, not used as the repository root.

## 2026-07-12 — Data policy

Include the author-supplied MGP-6 v2 diagnostic and annotations. Do not redistribute LongMemEval or 950 MB historical slices.

## 2026-07-12 — Historical runs

Exclude large model outputs and local databases from Git. Preserve source archives and publish selected immutable release assets separately when licensing and privacy checks pass.

## 2026-07-12 — Scoring

Canonicalize both sides of action comparison and both sides of semantic memory comparison. Report explicit eligible denominators for forgetting metrics.
