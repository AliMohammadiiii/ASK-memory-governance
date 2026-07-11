# M3-W11 MGP-6 Provenance

Date: 2026-05-21

## Artifact

Dataset: `data/mgp6_v1_seed0.jsonl`

SHA-256:

```text
12e17af530067f0ec1cefa1131898e2c8bd2414ef20cfc4c37fb936148e65701
```

Coverage:

```text
n=60
T1=10, T2=10, T3=10, T4=10, T5=10, T6=10
SUPERSEDE=30, ABSTAIN=22, KEEP=8
```

## Source Context

The prompt requested reusing real LongMemEval-S dialogue prefixes where
possible. The checked-in local LongMemEval file is still the Month-1 synthetic
placeholder: every row is a short synthetic coffee-preference exchange. It is
not the real released LongMemEval-S corpus and cannot supply enough realistic
prefixes for T1-T6.

For v1, each scenario therefore uses a LongMemEval-shaped two-turn prefix:
short user statement followed by assistant acknowledgement. The prefix style is
derived from the local LongMemEval schema and smoke files, not copied from
private or unreleased data. When the real LongMemEval-S release file is
available locally, this note should be updated with concrete borrowed
`session_id` values and the scenarios should be revised where useful.

The user-provided deep-research report at
`/Users/ali/Downloads/deep-research-report(7).md` informed the label policy:
first establish same subject and same semantic slot; then separate support,
contradict, and supersede by durable update evidence; route context-insufficient
or bundled candidates to unclear/abstain. The report also reinforced that
LongMemEval is a QA benchmark and a secondary context donor rather than a
native pairwise relation dataset.

## Per-Type Authorship Pattern

T1 scenarios are LongMemEval-style preference updates. Each starts with a
stable preference and adds a later replacement statement with explicit update
language such as "now", "switched", or "changed".

T2 scenarios are factual corrections. Each uses an atomic factual slot such as
appointment time, residence, name, room, or document date. The second statement
is authored as a correction or later authoritative update.

T3 scenarios stress stable-preference inertia. The initial memory is framed as
long-standing, and the perturbation is strong enough to justify replacement.

T4 scenarios stress ambiguity. They include hedges, role confusion, quoted
third-party statements, unresolved referents, or safety-sensitive uncertainty.

T5 scenarios stress transient scope. They include "tonight", "today",
"tomorrow only", "this quick check", "this shift", or "this one task".

T6 scenarios stress extraction confidence. The perturbation text names a
low-confidence extractor proposal and leaves the original memory unchanged.

## Scenario Prefix Register

All 60 rows use authored LongMemEval-shaped prefixes because no real
LongMemEval-S prefix corpus is present in this repository.

| Type | Scenario ids | Prefix source |
|---|---|---|
| T1 | MGP6-T1-01 through MGP6-T1-10 | Authored LongMemEval-shaped user preference + assistant acknowledgement |
| T2 | MGP6-T2-01 through MGP6-T2-10 | Authored LongMemEval-shaped user fact + assistant acknowledgement |
| T3 | MGP6-T3-01 through MGP6-T3-10 | Authored LongMemEval-shaped stable preference + assistant acknowledgement |
| T4 | MGP6-T4-01 through MGP6-T4-10 | Authored LongMemEval-shaped prior memory + assistant acknowledgement |
| T5 | MGP6-T5-01 through MGP6-T5-10 | Authored LongMemEval-shaped stable preference + assistant acknowledgement |
| T6 | MGP6-T6-01 through MGP6-T6-10 | Authored LongMemEval-shaped prior memory + assistant acknowledgement |

## Thesis Limitation Text

MGP-6 v1 is single-annotator and author-designed. It supports the Master's
controller evaluation but should not be presented as an independently validated
public benchmark. Real-prefix substitution and multi-annotator IAA are deferred
to the PhD dataset-paper expansion.
