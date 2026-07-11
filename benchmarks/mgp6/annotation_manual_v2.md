# MGP-6 v2 Annotation Manual

## 1. Annotation unit

Annotate one scenario as a write-layer memory-governance decision for one user and one atomic semantic slot. Judge three outputs separately: action, final memory state, and evaluation answer. Do not infer a broader user profile.

## 2. Decision tree

1. Is the candidate a reliable direct statement by the same user? If it is assistant speculation, quoted third-party speech, tool-only output, an extractor artifact, mixed unattributed text, or garbled evidence, choose `ABSTAIN`.
2. Does it clearly concern the same user, slot, and topic as the active memory? If not, choose `ABSTAIN`.
3. Is it atomic and self-contained? If it bundles claims or has an unclear pronoun or referent, choose `ABSTAIN`.
4. Is its scope temporary? A clear temporary override gives `KEEP`; preserve the durable record and optionally add a separate `transient_pref`. If temporary scope is also hedged or unreliable, choose `ABSTAIN`.
5. Is it a reliable durable same-slot contradiction? Choose `SUPERSEDE` even if no lexical change cue appears, provided the invalidation is inferentially certain.
6. Otherwise preserve the prior memory. Use `KEEP` only when the scenario supplies a valid non-durable addition; use `ABSTAIN` when evidence is insufficient for any write.

## 3. Direct versus inferred evidence

A first-person statement in a user turn is direct. A claim made by an assistant, tool, extractor, quoted speaker, or unidentified author is not converted into a user memory merely because it is fluent or carries a high confidence score.

Inference is permitted only after source identity and slot identity are secure. For example, a later statement that fixes a single standing default can invalidate a different earlier default without naming the earlier value. Do not infer from recommendations, co-occurrence, demographic stereotypes, or another person's behavior.

## 4. Same-slot matching and atomicity

Compare semantic meaning, not surface words. A routine drink default and a one-night drink choice are related but differ in temporal scope. A meeting time and meeting format are different slots. If the later utterance could refer to a different event, person, device, or preference dimension, abstain.

Each durable memory should be expressible as one `slot = value` record. Bundled candidates require decomposition outside this diagnostic; do not commit a partially supported bundle.

## 5. Durability cues

R4 cues such as `now`, `instead of`, `I switched`, `actually`, `please remember`, and `from now on` support a durable reading when source, slot, and content are otherwise valid. Cues are evidence, not a substitute for reasoning. A quoted sentence containing `from now on` is still not a direct-user update.

Absence of a cue does not force abstention. Apply the implicit-conflict rule in Section 12.

## 6. Temporary scope

Phrases such as `tonight only`, `today`, `for this task`, `this week`, `tomorrow only`, and `while traveling` normally mark a transient override.

- Clear and reliable: `KEEP` the durable memory and optionally add a separate active `transient_pref`.
- Temporary plus `maybe`, uncertainty, garbling, or unclear attribution: `ABSTAIN` and leave state unchanged.
- A durable standing-default statement is not T5 even if it is recent.

Never convert a temporary value into an active `stable_pref`.

## 7. Ambiguity and attribution

Use `ABSTAIN` for unclear pronouns, unknown speakers, shared-device logs without a principal, quoted speech, uncertain event identity, and vague same-slot relationships. The question is whether the candidate can justify a durable write, not whether the candidate sounds plausible.

Counterexample: a clear first-person correction of the same appointment time is T2 `SUPERSEDE`, not T4.

## 8. Confidence laundering

Model, extractor, tool, and pipeline confidence do not repair weak provenance. Inspect the underlying evidence. An extractor that converts `Maybe use dark mode once` into `screen_theme = dark theme, confidence 0.98` is a T6 abstention case.

MemEvoBench-style misleading pools motivate the failure pattern: repeated or polished text can increase apparent confidence without increasing user-origin evidence. The annotation remains `ABSTAIN`.

## 9. Quoted speech and assistant suggestions

Quoted preferences belong to the quoted speaker unless the user explicitly adopts them. Assistant offers and tool recommendations are proposals, not user attributes. Do not write them as durable memories. A later direct user confirmation can be evaluated as its own event, but it is absent from T6 rows.

## 10. Supersession lineage

For `SUPERSEDE`:

1. Keep the old record and set its status to `superseded`.
2. Add one active same-slot record with the current value.
3. Set the new record's `supersedes_id` to the old record's identifier.
4. Leave no stale active record for that durable slot.

Do not overwrite the old record in place and do not delete it. Lineage is part of the gold artifact.

## 11. Multiple active memories and duplicates

A stable slot has exactly one active stable preference. T5 can additionally contain one active transient record for an explicit temporary override. This does not create two durable defaults.

Do not add a second active durable record for a paraphrase. Semantically equivalent active records are duplicate writes. If a candidate merely repeats an existing durable value, future T7 policy applies; v2 does not contain T7 rows.

## 12. Implicit conflict

For T1-T3 cue-free rows, ask: would a competent reader agree that the later reliable statement fixes the same mutually exclusive slot and that the prior value can no longer be current?

- Yes: `SUPERSEDE`, tag `implicit_conflict` and `implicit_invalidation`, and preserve lineage.
- Genuinely uncertain: `ABSTAIN`; this is the T4 minimal-pair boundary.

Good implicit supersession: prior `calendar_week_start = Sunday`; later direct user statement `My standing calendar week start is Monday.` The same unique standing default cannot hold both values.

Counterexample: a shared note quotes that sentence without identifying its author. The content is similar, but attribution is insufficient, so abstain.

Never supersede merely because a sentence lacks an R4 cue, and never abstain merely because the cue is absent. Inferential certainty is the discriminator.

## 13. Query modes and answers

`direct_recall` asks for the current durable value. The expected answer states it.

`premise_resistance` embeds the stale or unsupported value as a false durable premise. The expected answer explicitly rejects that premise, states the active durable value, and contains no forbidden value. Merely answering yes or repeating the premise fails.

`implicit_application` poses a concrete task such as configuring a download,
booking a seat, or ordering a task list. The query must reveal neither the
active nor the stale value; the expected answer applies the active value and
must not name the stale or unsupported candidate. Reject meta-prompts such as
`Apply the user's preference` because they do not test natural use.

All modes are scored with GateMem-shaped regex criteria:

- every `judge_spec.include` pattern must match;
- no `judge_spec.not_include` pattern may match;
- the conjunction is the answer-level FAMA-style presence-and-absence score.

## 14. Examples and counterexamples

Durable change: prior `restaurant_noise_preference = quiet`; later direct user statement `I now prefer lively instead of quiet restaurants.` Annotate `SUPERSEDE`.

Temporary exception: the same prior memory; `For tonight only, use lively.` Annotate `KEEP`; retain quiet as durable and store lively only as transient if represented.

Hedged exception: `For this week, maybe use lively; I am not sure.` Annotate `ABSTAIN` and do not add a memory.

Unreliable extraction: a noisy fragment suggests lively and an extractor assigns 0.98 confidence. Annotate `ABSTAIN`.

Episodic correction: prior `project_deadline_date = May 12`; later direct user correction `Actually, the project deadline date is May 16, not May 12.` Annotate `SUPERSEDE` with an `episodic_fact` successor.

Bad supersession: changing a stable preference because of a one-night exception. Bad abstention: refusing a direct, reliable correction merely because the correction is cue-free.

## 15. Review procedure

Use `review/examples_review_sheet.csv`. Mark action correctness, memory-state correctness, and answer correctness independently. Put any disagreement or ambiguity in `review_notes`; do not silently edit the gold row during review. A revision should update the data, validator if needed, and changelog together.

For a minimal pair, also verify that both rows share the slot and prior active
value, the T4 row quotes the source claim, and only attribution or inferential
certainty changes the write decision. For an implicit-application row, verify
that the query cannot be answered without memory and does not reveal either
candidate value.

During model evaluation, reveal the evaluation query only after the write-stage
action and state are fixed. Annotation fields, judge patterns, rule identifiers,
and quality flags are reviewer metadata and must not be supplied in the default
closed-book track.
