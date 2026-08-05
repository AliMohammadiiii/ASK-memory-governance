# Data provenance and release boundaries

- MGP-6 v2 is author-created synthetic diagnostic data with the qualified CC BY
  4.0 grant in `LICENSE-DATA.md`.
- MGP-6 v4.3 is the current controlled diagnostic, but its public
  redistribution decision is not yet documented.
- LongMemEval is external and is never redistributed by this repository.
- Independent annotation rows and model-audit outputs are excluded unless their
  rights are explicitly cleared.
- Raw/private evidence stays outside the public release; public claims must be
  backed by allowed derived artifacts, cryptographic hashes, and reproducible
  scripts.
- The external MGP-Natural v0.1.0 candidate is pinned by SHA-256 and remains
  outside the source tree. Its 36 Wikipedia editorial-discussion items have
  provisional constructor labels only. The supplied 24/6/6 split is invalid for
  independent evaluation because continuity analysis yields components of 35
  and 1 items.
- MGP-Natural v0.1.1-derived is only a private blinding transformation. Its
  tracked audit and verification receipts contain aggregate evidence. Raw
  excerpts, source locators, provisional labels, secret, reveal map, and
  annotator submissions remain private.
- MGP-Natural v0.2.2 construction software is vendored as a separate Apache-2.0
  component. The supplied StudyChat and WikiConv `full` directory is a private
  derived workspace, not a raw-source archive. The tracked intake receipt has
  only aggregate counts and a nonsecret set commitment; it embeds no source
  payload, identifier, label, mapping, or secret and does not establish raw
  source integrity or a publishable benchmark.
- No external real-chat corpus is redistributed. The source matrix records
  access and rights risks, but a machine-generated GO/AMBER/RED decision is not
  legal or ethics approval.

Historical manifests remain immutable. Corrections are additive derived
manifests with explicit lineage.
