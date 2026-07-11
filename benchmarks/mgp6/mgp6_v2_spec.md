# MGP-6 v2 Diagnostic Specification

## 1. Purpose and positioning

MGP-6 v2 diagnoses whether a long-term memory controller makes the correct write-layer decision for one atomic semantic slot, produces an auditable memory artifact, and answers from the active state. It is an author-designed diagnostic slice and thesis-support artifact, not yet a public multi-annotator benchmark.

The diagnostic does not evaluate general QA over long histories, retrieval efficiency, multi-principal access control, deletion or active forgetting, emotional-support behavior, web-agent success, or production safety.

## 2. Vocabulary and decision output

V2 actions are `KEEP`, `SUPERSEDE`, and `ABSTAIN`. Memory types are `stable_pref`, `transient_pref`, and `episodic_fact`. Statuses are `active` and `superseded`.

`FORGET` and `forgotten` are reserved names for a future schema and never occur in v2 examples. `SUPERSEDE` means replacement with retained lineage, not deletion. `ABSTAIN` is a write-layer non-commit, not an answer-layer access refusal.

## 3. Taxonomy and exact distribution

| Type | Diagnostic condition | Rows | Gold actions |
|---|---|---:|---|
| T1 | preference drift over time | 30 | 30 SUPERSEDE |
| T2 | episodic factual correction | 30 | 30 SUPERSEDE |
| T3 | stable-preference replacement | 30 | 30 SUPERSEDE |
| T4 | ambiguity or referent uncertainty | 30 | 30 ABSTAIN |
| T5 | transient capture trap | 30 | 24 KEEP, 6 ABSTAIN |
| T6 | confidence laundering | 30 | 30 ABSTAIN |

Totals are 180 rows: 90 `SUPERSEDE`, 24 `KEEP`, and 66 `ABSTAIN`. This action imbalance is intentional. Report macro-F1 and per-action results rather than accuracy alone.

T1 is durable preference drift. T2 corrects one dated or scheduled fact. T3 is an explicit or inferentially certain standing-default replacement. T4 lacks reliable same-user, same-slot, atomic, or referential evidence. T5 distinguishes a temporary override from a durable preference. T6 rejects unsupported confidence from extractors, assistants, tools, mixed notes, and quoted sources.

## 4. Query-mode dimension

Every row has one query mode:

- `direct_recall`: ask for the current durable value.
- `premise_resistance`: embed the stale or unsupported value as a false durable presupposition; the answer must reject it and state the active value.
- `implicit_application`: pose a concrete task that can be completed only by using the active value, without mentioning either value in the query and without mentioning the stale or unsupported candidate in the answer. Meta-prompts such as "apply the user's preference" are invalid.

The exact corpus counts are 108 direct recall, 45 premise resistance, and 27 implicit application, corresponding to 60, 25, and 15 percent. Every type has at least three premise-resistance and two implicit-application rows. Every split has at least 15 percent premise resistance and 10 percent implicit application.

## 5. Cue-free conflict coverage

Each of T1-T3 contains 10 rows tagged `implicit_conflict`, `implicit_invalidation`, and hard or adversarial. Their perturbation events contain none of the R4 cue phrases `now`, `instead of`, `I switched`, `actually`, `please remember`, or `from now on`. The later direct-user statement still fixes a mutually exclusive current value for the same slot.

Exactly six cue-free rows per supersession type have a same-split T4 partner. The T4 partner preserves the source event verbatim inside an unattributed quote, preserves the prior active value, and forbids the source successor. Two additional explicit rows per type also have T4 partners, producing exactly 24 two-row minimal-pair groups.

## 6. Schema

Every JSONL object contains:

`scenario_id`, `version`, `type`, `subtype`, `difficulty`, `base_dialogue_prefix`, `initial_memory_state`, `perturbation_event`, `evidence_source`, `source_reliability`, `temporal_scope`, `semantic_slot`, `conflict_type`, `memory_age`, `gold_action`, `gold_memory_state`, `query_mode`, `evaluation_query`, `expected_answer`, `forbidden_answer_patterns`, `judge_spec`, `rationale_notes`, `annotation_rule_ids`, `template_family_id`, `minimal_pair_group_id`, `split`, and `quality_flags`.

A memory record contains `id`, `type`, `text`, `confidence`, `status`, `supersedes_id`, `valid_from`, `semantic_slot`, and `source`. Text uses the auditable form `slot = value`. Confidence is within `[0, 1]`.

`judge_spec` contains non-empty `include` regexes, `not_include` regexes, and notes. Required current content must match every include regex. Stale or unsupported content must match no not-include regex. In v2, `forbidden_answer_patterns` and `judge_spec.not_include` are equal.

## 7. State-transition invariants

- Every state has at least one active record.
- A slot containing stable preferences has exactly one active `stable_pref` record.
- Every `supersedes_id` points to a retained superseded record.
- `SUPERSEDE` retains the prior active record as `superseded` and adds one active successor pointing back to it.
- `KEEP` preserves the prior active durable record. A clear temporary override may be added only as a separate active `transient_pref`.
- `ABSTAIN` leaves the memory state byte-for-byte equivalent at the modeled field level.
- Answers contain an active value and contain no superseded or forbidden value.
- Duplicate equivalent active records are invalid.

## 8. Split policy

Train has 60 rows, dev has 30, and test has 90. Each type contributes 10, 5, and 15 rows. T5 contributes 8/2 KEEP/ABSTAIN to train, 4/1 to dev, and 12/3 to test.

Neither a `template_family_id` nor a `minimal_pair_group_id` may occur in more than one split. Scenario identifiers use `MGP6V2-{TYPE}-{SPLIT}-{NNN}`. Domains and query modes occur across splits, but near-duplicate construction families do not cross them.

Evaluation is two-stage. The write stage receives only the dialogue prefix,
initial memory state, and perturbation event. It commits an action and state
before the evaluation query is revealed. The answer stage then receives the
query and uses the predicted state. The default closed-book track withholds all
top-level annotations, gold fields, judges, rationales, rule identifiers,
split-blocking identifiers, and quality flags. An oracle-metadata ablation is a
separate track. This prevents query-conditioned governance and label leakage.

## 9. Annotation rules

- R1: require direct-user evidence; otherwise abstain.
- R2: require the same user, slot, and topic.
- R3: require an atomic, self-contained claim.
- R4: durable lexical cues include explicit change language.
- R5: a reliable durable same-slot contradiction supersedes.
- R6: a clear temporary override keeps durable memory; a hedged temporary candidate abstains.
- R7: low-confidence, garbled, or laundered evidence abstains.
- R8: expected answers use active memory only.
- R9: preserve superseded records for lineage.
- R10: do not create duplicate active memories for paraphrases.

Cue-free rows do not depend on R4. Their action follows inferential certainty under R1-R3 and R5.

## 10. Validation and quality control

Strict validation checks JSONL parsing, exact fields, schema types, confidence bounds, non-empty text, unique scenario and memory identifiers, identifier format, exact type/action/split/query counts, T5 distribution, query floors, difficulty floors, predecessor fidelity, one-successor lineage, active stable uniqueness, unchanged abstention states, byte-equivalent retained KEEP records, active-only answers, compiled judge regexes, stale-value exclusion, natural implicit-application non-leakage, cue-free coverage, release provenance flags, split leakage, exact two-row minimal-pair structure and value contrast, unique event surfaces, exact duplicate signatures, and simple email, phone, and street-address patterns.

The review sheet asks a reviewer to mark action, memory state, and answer correctness independently. A later multi-annotator release should report Cohen's kappa for two annotators or Krippendorff's alpha for more than two, plus artifact and semantic-answer agreement.

## 11. Metrics

Primary reports use all 180 rows; secondary reports use the 90 test rows. Metrics include action accuracy; per-action precision, recall, and F1; macro-F1; confusion matrix; artifact exact and semantic accuracy; over- and under-forgetting; stale-retrieval rate; five-condition lineage correctness; transient contamination; abstention precision and recall; invalid-commit and duplicate-write rates; premise-resistance rate; implicit-application accuracy; include, exclude, and joint judge scoring; FAMA-style presence-and-absence conjunction; implicit-conflict recall; explicit-cue recall; and cue-dependence gap.

If confidence is supplied, report a risk-coverage curve. Stratified bootstrap 95 percent intervals accompany metrics. Break down action accuracy, normalized artifact semantics, and answer presence-and-absence by type, query mode, subtype, and difficulty. Semantic artifact matching normalizes case, separators, and the auditable `slot = value` wrapper while exact matching retains every modeled record field. The optional paired McNemar helper compares action correctness for two prediction files.

## 12. Real-corpus grounding

The construction process inspected actual downloaded records rather than relying only on paper descriptions. LongMemEval supplied knowledge-update shapes and 30 question identifiers ending in `_abs` for false-premise resistance. Memora supplied operation chains and the distinction among add, update, delete, and no-memory sessions. GateMem supplied machine-readable include/not-include judge structure; its access-layer actions are not treated as MGP-6 write actions. MemEvoBench supplied named misleading-memory risk patterns for confidence laundering.

All released rows are newly authored synthetic paraphrases. The source corpora inform structure and failure modes, not personal content.

For external validity, run the same controller separately on the complete 78
LongMemEval knowledge-update questions and 30 `_abs` false-premise questions.
Report retrieval support recall separately from write governance. For controlled
MGP-6 comparisons, use B1 no-memory as a sanity floor, B2 as fixed-budget flat
retrieval, B3 as timestamp-only recency, and B4 as contradiction-driven naive
overwrite with no abstention safeguard. Equalize raw evidence, context budget,
retrieval unit, and query timing for all memory-using systems.

## 13. Release limitations

MGP-6 v2 is English-only, compact, synthetic, and single-author designed. It supports diagnostic claims about these controlled rows, not population-level claims or deployment guarantees. Naturalized surfaces remain templated compared with real conversations. Template blocking and row-level pattern provenance reduce known audit risks but cannot establish external validity or inter-annotator agreement.

## Appendix A. Future taxonomy, documented only

- T7: duplicate and paraphrase handling.
- T8: multi-session supersession chains.
- T9: transient-to-stable promotion.
- T10: stale-retrieval traps.
- T11: cross-domain leakage or unsafe use.
- T12: source and provenance conflict.
- T13: dedicated implicit-conflict block with mixed supersede and abstain labels.
- T14: explicit deletion using future `FORGET` and `forgotten` labels.

No T7-T14 row appears in the v2 JSONL.
