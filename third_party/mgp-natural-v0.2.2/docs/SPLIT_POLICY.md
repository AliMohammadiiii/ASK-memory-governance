# Continuity-Aware Split Policy

## Principle

A held-out item is valid only if no authoritative continuity component crosses train, development, and hidden test. Individual random splitting is prohibited.

## StudyChat continuity graph

Nodes are candidate items and relevant source records. Edges connect any of the following:

- the same pseudonymous user;
- the same chat;
- duplicate or overlapping dialogue history;
- exact or high-similarity prompt text;
- the same active artifact or dataset when it creates dependence;
- a strongly linked assignment template; or
- a cross-session preference chain.

At minimum, no StudyChat user may cross splits. Near-duplicate detection uses a pinned normalization and similarity threshold. Edge type and strength are retained for audit.

## WikiConv continuity graph

Edges connect:

- normalized page family;
- thread or section;
- contributor;
- revision lineage;
- deletion-restoration chain;
- quoted or duplicated discussion; or
- temporal adjacency that creates direct dependence.

Different exact page titles do not establish independence when they belong to one page family or lineage component.

## Assignment

Connected components are assigned under a deterministic seeded algorithm. The default target proportions are approximately 70 percent train, 15 percent development, and 15 percent hidden test. The optimizer minimizes size and available-stratum imbalance while treating component integrity as inviolable.

After independent gold exists, stratification can use action, scope, topic or editorial category, conversation length, evidence distance, transition type, and uncertainty. Before gold exists, no provisional constructor action may be used to tune a hidden-test split.

## Required audit

Each track reports:

- component count and size distribution;
- largest component and its share;
- component-to-split assignment;
- user, contributor, page-family, thread, lineage, and artifact overlap;
- exact-text and near-duplicate overlap;
- source-family overlap;
- item and component counts per split; and
- any target-balance shortfall caused by isolation constraints.

Any authoritative edge crossing invalidates the split. Group isolation is never relaxed to improve balance.

## Views and hidden test

The prevalence-preserving split is authoritative. A balanced diagnostic action view may be generated after adjudication but is not a replacement split and must be labeled diagnostic. Hidden-test labels and model performance cannot be inspected during construction, guideline revision, or model tuning.

## Current execution

The sample-derived StudyChat split is a private pilot diagnostic only. Its user-disjoint audit can validate code behavior, but it is not a full-corpus held-out release. The WikiConv split implementation is tested with synthetic fixtures; no natural WikiConv split exists in this execution.

