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

## Claim boundary

The supported contribution is a layered diagnostic and a reproducible validity
audit for typed write decisions, explicit supersession lineage, and first-class
abstention. The release does not claim that any individual component is new,
that KSA is the first memory-governance system, that the reference policy is
superior, that zero observed false commits implies population safety, or that it
improves LongMemEval.
