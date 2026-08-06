# Limitations

## Evidence scope

MGP-6 v2 is a synthetic, author-designed 180-item diagnostic. Its held-out split
does not establish construct validity: conflict type deterministically predicts
the gold action and a conflict-type-only lookup fitted on train+development
reaches 1.000 accuracy on the 90-item test split (type-only: 0.9667). The split
prevents exact template-family overlap but does not prevent label leakage or
controller--dataset circularity. It cannot estimate performance on natural user
populations, languages, domains, or long deployment histories.

One independent human annotator labelled the test split; agreement with author
gold was high, but this is not multi-annotator human inter-annotator agreement.
A four-model panel is an audit, not a replacement for human annotation. The
prospective v3 protocol requires independent data authors and three blinded
human annotators; that protocol has not yet been executed.

MGP-Natural v0.1.0 is a separate 36-item feasibility seed built from Wikipedia
editorial-discussion excerpts. It contains 76 normalized excerpt rows, not 76
verified native dialogue turns. All actions are single-curator provisional
labels. The supplied blind packet exposes a field that recovers all 36 labels,
and direct source IDs join it to the seed. The corrected derived packet removes
those fields, but no independent annotation has yet occurred.

The declared 24/6/6 split is not suitable for held-out reporting. Linking items
by shared page family or contributor yields only two continuity components with
sizes 35 and 1. No split of this seed can provide three independent partitions.
The seed therefore cannot support confidence intervals, leaderboard ranking,
population claims, or a natural personal-assistant performance result. Source
selection and exact text normalization also lack a complete reconstruction
ledger.

MGP-Natural v0.2.2 adds a two-track construction implementation for StudyChat
and WikiConv, but the supplied `full` directory is a private derived workspace,
not the original raw-source archive set. Its aggregate receipt records 16,851
StudyChat rows, 431 redacted StudyChat construction items, and 54 redacted
WikiConv construction items. These are workflow counts, not independent gold
examples or a performance result. Raw-source integrity is unverified, the
workspace contains private blinding material, and all legal, manual-privacy,
protocol-freeze, independent-annotation, adjudication, and continuity-split
gates remain open. There is no mixed-track headline score.

The MGP-6 system rows are mostly single-run evaluations. Template-family and
minimal-pair cluster bootstrap better reflect within-collection dependence but
cannot repair external-validity or data-generation bias. The intervals do not
capture model, prompt, provider, or seed variation. External-system adapters expose unequal
action spaces. Mem0, Letta, and Graphiti results therefore require the published
`NOOP -> ABSTAIN` mapping disclosure. The MemOS adapter cannot express observed
supersession in this harness and is diagnostic only.

## No final LongMemEval result

No LongMemEval value in this release is a final-candidate result. The v7
controller run is contaminated by provider failures, cached empty extraction
fallbacks, manual relaunches, and a no-op escalation tier. Its 61.1% controller
accuracy and the 63.3% naive-overwrite result are diagnostic only.

The 77.2% value is a selection-biased failure-replay construction: it carries
forward 110 v7 successes and re-evaluates only the 70 v7 failures under a
different pipeline/judge composition, followed by four model-assisted
overrides. It is not a complete v8 run. A non-empty v8 top-up re-evaluated 84 of
the 110 carried-forward items; only 71 remained correct and 13 regressed.
Combined with the replay, this yields 96/154 raw observed and a possible
full-180 raw range of 53.3%-67.8%. The frozen final-1.1 homogeneous run could not
start because the supplied OpenRouter credential returned HTTP 403. It remains
`externally_pending`.

Single-session preference findings are mechanism-generating diagnostics from
one contaminated run. The apparent v7 score of 11/30 is not preserved under the
top-up: 8/29 are observed correct with one unresolved, so the maximum for that
attempt is 9/30. Proposed SSP interventions have not been implemented or tested.

## System and deployment limits

KEEP/SUPERSEDE/ABSTAIN is a deliberately small write-action space. Real systems
may need merging, confidence revision, scoped expiration, multi-party ownership,
legal deletion, or policy-specific retention. Typed records and lineage improve
inspectability but do not guarantee factuality, privacy, fairness, or safe use.
The reference SQLite store is not a production multi-tenant service, and no
production database access is required or supported by the evaluation workflow.

Hosted behavior can vary by model version, provider implementation, capacity,
content policy, and account permissions even when the public model identifier is
unchanged. The release therefore records requested and actual model/judge IDs,
fallbacks, hashes, and provider policy; those records reduce but cannot eliminate
provider drift.

## Licensing and privacy

LongMemEval is external and not redistributed. The public package also withholds
the independent annotator's two raw per-item CSVs until redistribution consent is
documented; only aggregate, non-identifying statistics and source hashes are
retained. Model-generated rationales may be subject to upstream provider terms.
See `LICENSE-DATA.md`.

The MGP-Natural parent archive and derived private packet are not public-release
artifacts. Wikipedia-derived excerpts require revision-specific attribution,
share-alike, modification-notice, and privacy review. Candidate real-chat
corpora have source-specific restrictions and are not included merely because
their metadata advertises an open license.

The vendored MGP-Natural v0.2.2 software is Apache-2.0 code only. It conveys no
rights to its source conversations, annotations, mappings, or derived text.

## Claim boundary

The supported contribution is a layered diagnostic and a reproducible validity
audit for typed write decisions, explicit supersession lineage, and first-class
abstention. The release does not claim that any individual component is new,
that ASK is the first memory-governance system, that the reference policy is
superior, that zero observed false commits implies population safety, or that it
improves LongMemEval.
