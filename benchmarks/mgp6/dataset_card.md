# Dataset Card: MGP-6 v2 Diagnostic

## Summary

MGP-6 v2 is a 180-row, author-designed diagnostic slice for write-layer governance in long-term AI-assistant memory. Each synthetic scenario isolates one atomic semantic slot and labels a controller transition as `KEEP`, `SUPERSEDE`, or `ABSTAIN`. Evaluation covers the action, resulting memory artifact, supersession lineage, and answer behavior.

The artifact supports a Master's thesis method and internal evaluation. It is not yet a public multi-annotator benchmark.

## Composition

There are 30 rows per type: T1 preference drift, T2 episodic factual correction, T3 stable-preference supersession, T4 ambiguity or referent uncertainty, T5 transient capture, and T6 confidence laundering. Gold totals are 90 `SUPERSEDE`, 24 `KEEP`, and 66 `ABSTAIN`.

Splits contain 60 train, 30 dev, and 90 test examples, with 10, 5, and 15 rows per type respectively. Template families and minimal-pair groups are split-blocked. Query modes total 108 direct recall, 45 premise resistance, and 27 implicit application. All 27 implicit-application prompts are task-shaped rather than meta-instructions, and all 30 cue-free supersession events use natural surface language.

## Construction and grounding

Examples were authored as synthetic paraphrases after targeted inspection of:

- LongMemEval knowledge-update and false-premise question forms.
- Memora add, update, delete, and multi-session operation structure.
- GateMem `judge_spec` include/not-include regex structure and leakage targets.
- MemEvoBench misleading-memory pools and named risk patterns.

No source record is copied verbatim. No real name, address, email, phone number, or other real personal data is used. Domains are low risk: preferences, routine settings, generic schedules, study and work organization, shopping, household routines, and media choices.

Row-level `quality_flags` record pattern lineage: LongMemEval knowledge-update
and false-premise forms, STALE-style implicit conflict and application,
Memora-style temporal scope, MemEvoBench-style misleading pools, and the
GateMem-shaped judge. These are construction metadata, not controller inputs.

## Annotation policy

Reliable, durable, direct-user same-slot contradictions are superseded with explicit lineage. Clear temporary overrides keep the durable memory and may add a separate transient record. Ambiguous attribution, unclear referents, hedged temporary claims, assistant inferences, tool-only suggestions, extractor artifacts, and garbled sources cause abstention.

Cue-free T1-T3 conflicts are superseded only when a competent reader would agree that the later same-slot statement cannot coexist with the earlier value. Their T4 partners remove reliable attribution or certainty and therefore abstain.

## Intended use

- Diagnose memory-controller write decisions and auditable state transitions.
- Compare action behavior with artifact and answer behavior.
- Measure stale retrieval, invalid commits, transient contamination, premise resistance, and cue dependence.
- Support controlled thesis experiments and error analysis.
- Pair controlled write-layer results with the complete 78 knowledge-update and
  30 `_abs` LongMemEval subsets for an external-validity check.

## Out-of-scope use

Do not use MGP-6 v2 to claim broad assistant quality, real-user safety, demographic fairness, access-control correctness, deletion compliance, retrieval scalability, or leaderboard superiority. It is not a source of factual or personal profiles and should not train a production user model.

## Limitations and ethics

The data is synthetic, English-only, compact, and single-author designed. Type balance is diagnostic while action balance is intentionally unequal. Surface naturalization does not make the corpus conversationally representative. The test split reduces template leakage but does not replace external validation. Human review columns are supplied and synchronized with this release, but multi-annotator agreement has not yet been measured. Any public benchmark claim would require independent annotation, adjudication, documented agreement, broader domains, and a release review.

## Citation

Citation placeholder: author, thesis title, institution, and year to be added after thesis deposit.
