# Dataset Card: MGP-Natural

## Release status

`PRIVATE_CONSTRUCTION_REPOSITORY; NATURAL GOLD AND PUBLIC RELEASE PENDING`

This card describes the intended benchmark and the evidence currently available. It is not a public data release notice.

## Motivation

Long-lived conversational systems must decide what to write, not only what to retrieve or answer. MGP-Natural targets candidate-level write-time governance over natural conversations: preserve a standing state, replace it, or withhold commitment. It additionally supervises evidence, resulting state, and lineage.

## Task contract

Each item contains one state-bearing principal, one atomic slot, a prior standing value, ordered dialogue, a later candidate turn, and sufficient local context. The target is `KEEP`, `SUPERSEDE`, or `ABSTAIN`; invalid cases are excluded rather than forced. See `docs/TASK_DEFINITION.md`.

## Source tracks

### StudyChat

Natural human-LLM educational task conversations. Supported scopes include session and cross-session task state, artifact state, corrections, uncertainty, and explicit interaction preferences. The attached input in this execution is a sample derivative.

### WikiConv

Natural human-human Wikipedia editorial conversations and revision lineage. Supported scopes include wording, inclusion, removal, sources, consensus, disputes, revisions, deletion-restoration, and editorial uncertainty. WikiConv is not personal-assistant memory. No natural WikiConv artifact is processed in this execution.

## Unit of analysis

One write-time decision over one principal, scope, and slot. Related items may form explicit lineage or trajectories, but each classification item remains atomic.

## Source provenance

Input and source manifests record origin, access date, version evidence, size, hashes, schemas, and acquisition status. StudyChat access must be separately authorized. WikiConv source evidence distinguishes wrapper and underlying comment terms. Private source mappings are not released to annotators.

## Candidate construction

StudyChat uses deterministic high-recall signals followed by conservative semantic construction. WikiConv uses supported action and revision lineage while separating discussion, consensus, and committed page state. Every accepted constructor action is provisional. Reason-coded rejection logs preserve auditability.

## Annotation and adjudication

The prospective protocol requires at least three independent annotators per valid item, immutable rows, blind source identity, and a separate additive adjudicator. Gold cannot be built from constructor labels. No human annotation or adjudication has been performed in this execution.

## Privacy

The pipeline performs deterministic scanning and redaction for identifiers, secrets, paths, timestamps, educational information, usernames, repositories, and sensitive or deleted content. It creates a private review queue and redaction log. Automated scanning does not guarantee anonymity; manual review is mandatory.

## Licensing

Code is licensed under Apache-2.0. Source data, annotations, and benchmark derivatives are excluded from that code license unless a later recorded decision states otherwise. StudyChat terms, underlying conversation permissions, annotation consent, WikiConv wrapper terms, comment-text terms, attribution, ShareAlike, modifications, and deleted-content handling are tracked separately. Legal approval is pending.

## Splits and continuity

StudyChat uses user-disjoint continuity components. WikiConv uses page, contributor, thread, revision, and lineage components. No authoritative component may cross train, development, or hidden test. The current StudyChat split is **blocked and invalid for held-out evaluation**: both surviving candidates belong to one continuity component, leaving development and hidden-test empty. No natural WikiConv split exists.

## Statistics

Observed source and construction statistics are generated into `reports/` from pinned artifacts. The available derivative reconstructs 4,745 interactions in 222 chats across 70 pseudonymous users and yields two provisional uncertainty candidates plus 4,743 reason-coded rejections. These counts describe only the supplied derivative. Aggregate values in `stats.json` are source metadata, not locally available full-corpus records. No natural WikiConv count or unsupported headline number is embedded in this card.

## Evaluation

Primary per-track metrics are macro-F1, accuracy, class metrics, and confusion matrices. Secondary metrics cover evidence, resulting state, lineage, joint exact match, coverage, calibration, and selective risk. Cluster-aware confidence intervals are required. There is no mixed headline score.

## Intended use

Research on write-time state governance, uncertainty, evidence attribution, state reconstruction, cross-domain transfer, trajectory integrity, and memory-controller evaluation.

## Out-of-scope use

Identity inference, surveillance, profiling, automated grading, disciplinary decisions, reconstruction of deleted content, certifying a system as safe, or claims that the benchmark represents all personal memory or all natural conversation.

## Known failure modes

Ambiguous slot boundaries, implicit preferences, source-history omissions, proposal-versus-implementation confusion, privacy-destructive redaction, large continuity components, class imbalance, source-specific shortcuts, and propagation of early trajectory errors.

## Maintenance and versioning

Schemas, protocols, source manifests, claims, and release decisions are versioned. Any change after annotation freeze requires an amendment. Source and venue snapshots are dated and refreshed before release.

## Access

This repository contains code, documentation, synthetic fixtures, and private local derivatives. Raw and identity-bearing data are git-ignored. Public packaging remains blocked until all required human and scientific gates pass.

## Citation

Use `CITATION.cff` for the software scaffold. A dataset citation and DOI must not be created until release is explicitly authorized.

