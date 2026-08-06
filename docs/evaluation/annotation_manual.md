# MGP-6 Annotation Manual

Version: v1 seed0

## Purpose

MGP-6 is a reduced 60-scenario perturbation slice for testing memory
governance decisions: `KEEP`, `SUPERSEDE`, and `ABSTAIN`. It is not a public
multi-annotator benchmark. It is a Master's-method support artifact authored by
one annotator and designed to exercise failure modes before Month-4 evaluation.

## Scenario Types

T1, preference drift over time: the user states a preference, then later
modifies or replaces it. Gold action is `SUPERSEDE` when the later statement is
about the same subject and semantic slot and has durable update evidence.

T2, episodic fact contradiction: two user factual claims conflict on the same
slot, and the second claim is a correction or later authoritative state. Gold
action is `SUPERSEDE`.

T3, superseding stable preference: a long-standing preference is replaced by a
new explicit assertion. Gold action is `SUPERSEDE`. Require stronger update
evidence than T1 because the prior is intentionally stable.

T4, abstention under ambiguity: hedges, negation ambiguity, role confusion,
quoted speech, or referent uncertainty make the candidate unsafe to apply. Gold
action is `ABSTAIN`.

T5, transient capture trap: a short-lived preference or one-off instruction
could be mistaken for a stable memory. Gold action is `KEEP` when it should be
stored only as transient while preserving the stable prior, or `ABSTAIN` when
the transient candidate is too hedged to store.

T6, confidence laundering: a low-confidence extraction could be treated as a
strong downstream update. Gold action is `ABSTAIN`.

## Decision Tree

1. Is the candidate a direct user assertion?
   If it is assistant speculation, quoted third-party text, or an extractor
   artifact without a clear user assertion, choose `ABSTAIN`.

2. Do the prior and candidate refer to the same subject and same semantic slot?
   If subject or slot matching is unsafe, choose `ABSTAIN`.

3. Is the candidate atomic?
   If it bundles multiple memories, lacks enough context, or mixes possible
   referents, choose `ABSTAIN`.

4. Is there durable update evidence?
   Signals include explicit correction, "now", "instead of", "switched to",
   later-session chronology, or a stated routine change.

5. If the same slot conflicts and durable update evidence exists, choose
   `SUPERSEDE`.

6. If the candidate is time-bounded, task-bounded, or event-bounded, preserve
   the stable prior. Choose `KEEP` with a transient memory if the assertion is
   clear; choose `ABSTAIN` if it is also hedged or low-confidence.

7. If extractor confidence is low or the evidence is transcript noise, choose
   `ABSTAIN` even if the candidate superficially contradicts a prior.

## Common Pitfalls

Do not treat lexical negation alone as supersession. "Maybe I do not like Thai
food tonight" is not the same as "I now prefer Vietnamese food instead of Thai."

Do not overwrite stable preferences with one-off instructions. "For this quick
check, answer yes or no" is a transient instruction, not a replacement for a
general preference for detailed answers.

Do not infer the user's preference from an assistant suggestion. The user must
assert it.

Do not resolve pronouns optimistically. If "he moved" could refer to a brother
or cousin, abstain.

Do not launder low extraction confidence. If the scenario says the extractor
confidence is low, the gold action is `ABSTAIN` unless the user later provides
a separate clear assertion.

## T4 vs T5 vs T6

T4 is about semantic ambiguity. The turn itself is unclear even before scoring:
role confusion, hedging, conflicting clauses, or unclear referents.

T5 is about temporal scope. The turn can be clear, but it is explicitly limited
to tonight, tomorrow, this task, this shift, or another short window.

T6 is about upstream extraction reliability. The proposed candidate may look
like a clean memory after extraction, but its source evidence is low-confidence,
garbled, quoted, or misread.

If a case fits more than one bucket, use the most diagnostic type:
`T6` for low-confidence extraction artifacts, `T4` for semantic ambiguity, and
`T5` for clear but transient scope.

## Gold Memory State Rules

For `SUPERSEDE`, keep the prior item in `gold_memory_state` with
`status="superseded"` and create a new active item whose `supersedes_id` points
to the prior id.

For `KEEP` in T5, retain the stable prior and add a separate
`transient_pref` item only when the transient assertion is clear enough.

For `ABSTAIN`, leave `gold_memory_state` identical to the active prior state.

Memory text should be one short canonical sentence. It should preserve
negation, uncertainty, and temporal scope when those are part of the memory.

## Limitations

This v1 slice has a single annotator: the system designer. It is therefore
useful for internal controller evaluation and thesis methodology, but not for a
public dataset claim. Multi-annotator expansion and Cohen's kappa are deferred
to the PhD-scale dataset paper.
