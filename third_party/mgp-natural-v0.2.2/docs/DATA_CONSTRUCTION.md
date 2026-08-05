# Data Construction Protocol

## Status of this execution

The supplied StudyChat archive is an audit sample derivative, not a complete corpus export. It contains 1,000 candidate rows and 100 sampled long-chat records. The included `stats.json` describes a larger source corpus, but those totals are metadata rather than rows available to this execution. The complete-corpus gate remains blocked.

Real WikiConv acquisition is not performed in this execution. The repository records official source evidence, provides a resumable and hash-checking acquisition interface, and tests reconstruction against synthetic rights-cleared fixtures. A natural WikiConv candidate count cannot be reported from fixtures as observed corpus yield.

## Evidence-first construction

Construction begins with an immutable input inventory. The audit records archive and member hashes, sizes, row counts, schemas, missing fields, overlap, identity and continuity fields, cumulative-history behavior, and privacy-sensitive field classes. Source-derived observations are separated from assumptions and external research.

The implementation uses canonical JSON serialization, stable sorting, atomic writes, and SHA-256 manifests. Private identity-bearing artifacts are mode `0600`; private directories are mode `0700`.

## StudyChat reconstruction

Rows are grouped by pseudonymous user and chat, then ordered by `interactionCount` and stable row index. Prompt-response rows are canonical. Timestamps are consistency signals only. Repeated cumulative `messages` are checked against the reconstructed prefix and never treated as independent conversations.

The reconstruction audit records:

- duplicate source rows;
- missing or repeated interaction counts;
- non-monotonic counts;
- histories beginning after interaction zero;
- changed prior prompts or responses;
- omitted prefix turns;
- candidate prompt misalignment;
- chat or user boundary inconsistencies; and
- partial histories.

No chronology conflict is silently repaired. A reconstructed chat can be retained for audit while affected candidate rows are rejected with `SOURCE_INCOMPLETE` or `INSUFFICIENT_CONTEXT`.

## Two-stage StudyChat mining

### Stage 1: deterministic retrieval

A high-recall signal layer detects correction language, replacement language, reaffirmation, uncertainty, preference statements, file or dataset references, rollbacks, format constraints, response-policy changes, and task-state changes. Signal matches are retrieval aids, not labels.

### Stage 2: semantic construction checks

The constructor requires an earlier attributable standing value for the same principal and slot; chronological precedence; atomic prior and candidate values; adequate context; plausible future relevance; and privacy-preserving interpretability. It rejects keyword-only assignment language, social acknowledgments, unrelated requests, missing predecessors, unresolved replacements, and multi-slot candidates.

Accepted records receive only a provisional constructor action. Each retained item remains `PENDING_HUMAN_REVIEW`. Rejections are written to a reason-coded log rather than silently discarded.

## StudyChat cross-session policy

Cross-session items require the same pseudonymous user in at least two independently reconstructed chats and explicit preference evidence. Passive behavior is insufficient. A cross-session candidate must be supported by repeated explicit preference, explicit correction of an earlier preference, or explicit continuation language. Assignment templates and copied instructions are screened through continuity and near-duplicate links. Stable source identity is never released to annotators.

## WikiConv reconstruction and construction

WikiConv source actions are reconstructed while preserving creation, addition, modification, deletion, restoration, reply relation, thread, section, page, contributor, and revision order when supported by the source representation. Private provenance records the source action and its parent or ancestor.

Construction distinguishes three layers:

1. discussion state, such as proposal, support, opposition, dispute, or uncertainty;
2. committed page state; and
3. source revision action.

A proposal is not treated as implementation without revision evidence. A revision is not treated as consensus without discussion evidence. Deletion and restoration maintain explicit lineage. Unsupported or broken parentage is excluded.

## Privacy transformation

Automated scanning detects emails, IP addresses, URLs, tokens and secret-like strings, usernames, repository names, paths, precise timestamps, institutional and educational identifiers, names, grades, submissions, and sensitive or deleted Wiki text. Findings store pattern type, location, and hashes rather than matched strings in public reports.

Deterministic redaction creates a separate derivative and an append-only private redaction log. Automated scanning is triage, not an anonymity guarantee. Every candidate remains blocked pending manual privacy review.

## Blinding

Blind IDs are derived with HMAC-SHA256 under a fresh 256-bit secret by default. Externally supplied secrets below 128 bits are rejected. The secret and private mapping are excluded from the packet. Nested prohibited-key scanning examines every object and array, and the ZIP is built from an allowlist. Publicly recorded commitments permit later integrity checks without revealing mappings.

## Annotation and adjudication boundary

Constructor judgments are not exported to annotators. At least three independent annotators label each valid item. Adjudication is additive, uses immutable original-row hashes, and is performed by someone outside the original annotator set. Gold construction is disabled until independent annotation, adjudication, privacy, split, mapping-reveal, and release approvals are all recorded.

## Continuity-aware splitting

The continuity graph is constructed before splitting. StudyChat connects shared users, chats, overlapping histories, exact and near-duplicate prompts, artifacts, assignment templates, and cross-session chains. WikiConv connects page families, threads or sections, contributors, revision lineage, deletion-restoration chains, quoted or duplicate discussion, and dependent temporal neighborhoods.

Connected components, not items, are assigned to train, development, and hidden test. StudyChat user disjointness and WikiConv component disjointness are authoritative constraints. Stratification is best effort and may never break isolation.

## Reproducibility outputs

Every stage emits a machine-readable report, hashes, counts, and status. The pipeline is deterministic under pinned input, code, protocol, seed, and private reveal record. Raw, gated, private, and identity-bearing data are excluded from version control and public packaging.

