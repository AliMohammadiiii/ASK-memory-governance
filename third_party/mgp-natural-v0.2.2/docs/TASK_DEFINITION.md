# MGP-Natural Task Definition

## Scientific object

MGP-Natural is a multi-domain natural-conversation benchmark for candidate-level write-time memory governance. Each item asks whether a newly observed candidate statement should preserve a standing state, replace it, or cause the system to withhold a state commitment. The benchmark also supports attributable evidence, resulting-state reconstruction, and explicit lineage.

The unit of analysis is one atomic decision over one state-bearing principal, one scope, and one memory slot. It is not a generic next-response task, a factual question-answering task, or a test of whether any text is worth storing.

## Source tracks

The benchmark maintains two separate source tracks.

- `STUDYCHAT` contains natural human-LLM task, artifact, correction, uncertainty, and interaction-preference state. A StudyChat item is not automatically a claim about durable personal memory.
- `WIKICONV` contains natural human-human collaborative editorial state and revision lineage. It is not modeled as personal-assistant memory.

The tracks share the action ontology and validation framework, but they have separate manifests, continuity graphs, splits, statistics, evaluation tables, privacy analyses, license analyses, limitations, and headline metrics. No mixed headline accuracy is defined.

## Decision contract

### KEEP

Preserve the standing state because the candidate provides attributable and sufficiently clear evidence that supports, reaffirms, or remains compatible with the current value. `KEEP` leaves the canonical standing value unchanged.

### SUPERSEDE

Replace the standing state because the candidate explicitly and clearly updates, corrects, reverses, restores, deletes, or otherwise replaces the prior value for the same principal, scope, and slot. Every `SUPERSEDE` item requires a nonempty resulting value that materially differs from the prior value.

### ABSTAIN

Make no state commitment because the evidence is conditional, speculative, ambiguous, disputed, insufficient, or referentially unsafe. `ABSTAIN` preserves the prior canonical state, but unlike `KEEP`, does not affirm that state.

### EXCLUDE

`EXCLUDE` is a construction or annotation status, never a model action. An item is excluded rather than forced into a target class when its predecessor is non-atomic, its slot or principal changes, context or chronology is inadequate, the resulting value is unresolved, privacy-safe publication destroys the task, or the decision admits multiple equally defensible interpretations.

## Required observable fields

A valid item exposes:

1. a state-bearing principal type;
2. an atomic memory or state slot;
3. a prior standing value;
4. ordered conversational evidence;
5. a chronologically later candidate turn;
6. sufficient local context to interpret the candidate; and
7. no hidden metadata that reveals the action.

Private construction records additionally retain source provenance, continuity keys, provisional constructor judgments, and privacy status. Those private fields are removed before blinding.

## Atomicity and temporal requirements

The prior value must be affirmative, attributable, canonicalizable, and standing before the candidate. Questions, alternatives, vague placeholders, or bundles of unrelated state are invalid predecessors. The candidate must address the same slot and principal, occur after all predecessor evidence, and support exactly one primary decision.

A `SUPERSEDE` resulting value must be explicit or reliably canonicalizable from released context. It may not depend only on source metadata. `KEEP` and `ABSTAIN` preserve the prior canonical value even though their semantics differ.

## Scope labels

StudyChat scopes include:

- `SESSION_TASK_STATE`
- `CROSS_SESSION_TASK_STATE`
- `SESSION_INTERACTION_PREFERENCE`
- `CROSS_SESSION_USER_PREFERENCE`
- `ARTIFACT_STATE`
- `CORRECTION_STATE`
- `UNCERTAINTY_STATE`

WikiConv scopes include:

- `EDITORIAL_DECISION`
- `CONTENT_INCLUSION`
- `CONTENT_REMOVAL`
- `WORDING_STATE`
- `SOURCE_STATUS`
- `CONSENSUS_STATE`
- `DISPUTE_STATE`
- `REVISION_STATE`
- `DELETION_RESTORATION`
- `EDITORIAL_UNCERTAINTY`

Scope is part of the task definition and must be reported in all slice analyses.

## Primary and secondary outputs

The primary output is exactly one of `KEEP`, `SUPERSEDE`, or `ABSTAIN`. Secondary structured outputs are:

- evidence turn IDs;
- resulting value;
- optional calibrated confidence;
- lineage relation; and
- trajectory state after applying the decision.

Supported lineage relations are `REAFFIRMS`, `SUPERSEDES`, `WITHHOLDS_COMMITMENT`, `RESTORES`, `DELETES`, `RESOLVES`, `REOPENS`, and `CONTRADICTS_WITHOUT_RESOLUTION`. The richer lineage relation is secondary supervision and does not expand the three-class action target.

## Research questions

The repository is designed for in-domain decision quality, structured state reconstruction, evidence attribution, cross-domain transfer, scope sensitivity, uncertainty and calibration, and chronological trajectory integrity. It can represent these studies before natural adjudicated gold exists, but no empirical answer is claimed until the corresponding protocol and evidence gates pass.

## Non-goals and invalid shortcuts

The source `llm_label` in StudyChat is not an MGP target and may only support sampling, corpus description, retrieval assistance, and mining diagnostics. Page revisions alone do not establish editorial consensus, and discussion proposals alone do not establish committed page state. Constructor labels are never gold. Exact filenames, source IDs, user IDs, page IDs, revision IDs, and continuity metadata are never model inputs.

