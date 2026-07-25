# Single-Session-Preference (SSP) Failure Analysis — LongMemEval-M / ASK controller

**Scope.** Error analysis of the `single-session-preference` competency in the
ASK memory-governance controller's LongMemEval-M evaluation. Evidence-first: every
number below is recomputed from the run's `judgments.jsonl`, and every failure
classification is checked against the *constructed prompt* (`raw_prompt`) to see
whether the decisive fact was actually available to the answerer.

## 1. Evidence base

| Role | Path |
|------|------|
| v7 base run (merged 180 items) | `ask_controller/runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v7/controller/` |
| SSP questions / gold answers | `…/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v7/range_0_179.jsonl` |
| Failure replay (70 items) | `ask_controller/runs/lme_m last version/lme_m_modal_qwen35_9b_v8_failures_nothink/controller/` |
| Adjudicated merge | `ask_controller/runs/lme_m last version/lme_m_v8_failure_replay_adjudicated/` |
| Machine-readable taxonomy | `artifacts/single_session_preference_error_taxonomy.json` |

## 2. Verified headline numbers

- **SSP is 11/30 correct in contaminated v7** (accuracy **0.3667**). This is a
  diagnostic reference, not a final or transferable score. It is recomputed directly from
  `controller/judgments.jsonl` filtering `competency == "single-session-preference"`.
- **Bootstrap 95% CI: [0.20, 0.53]** (stratified percentile bootstrap, n=20000,
  seed=0; single competency stratum). Reproduce with
  `scripts/evaluation/evaluate_single_session_preferences.py`.
- **19 persistent failures.** All 19 are the SSP items scored incorrect in v7.
- **Failure replay repaired 0/19.** The replay run selected exactly the same 19
  SSP failures and none flipped to correct (`replay_ids_equal_base_failure_ids: true`
  in the replay `summary.json`; SSP subset = 19 items, 0 correct). The replay used
  changed prompts/contexts and therefore cannot isolate an answer-model effect;
  it is failure-localization evidence only.
- **The four model-assisted overrides did not touch SSP.** They covered
  overrides (knowledge-update, single-session-user, temporal-reasoning,
  multi-session); **0** were SSP items. The independent top-up instead observed
  **8/29** correct with one unresolved item, so the most favorable full total is
  **9/30**. The v7 11/30 count cannot be carried across configurations.

## 3. Methodology

1. Selected the 30 SSP items by `competency == "single-session-preference"`
   (n=30 in both the slice and the judgments; counts agree).
2. For each of the 19 failures, read the question, gold answer, controller answer
   (`answers.jsonl` / mirrored in `judgments.jsonl.predicted`), and the judge
   rationale.
3. **Root-cause localization by context inspection.** For every failure I checked
   whether (a) the gold's decisive fact and (b) the model's chosen fact appear in
   the *constructed* `raw_prompt`, and whether the item's `supporting_session_ids`
   turn survived retrieval + trim. This is the key discriminator: a failure is a
   *retrieval/context* break when the decisive gold turn never reached the prompt,
   and an *answer-realization/binding* break when it did but the model answered
   off-rubric anyway.
4. Assigned each item a **primary** category (+ optional **secondary**) from the
   fixed candidate taxonomy, and localized it to one or more **pipeline layers**.
   Only categories that actually occur are reported.

This matches, at finer grain, the v7 `ANALYSIS_REPORT.md §3.3` observation that
SSP failures show "rubric-shaped profiles with off-rubric or fabricated
specifics" — the profiles are shaped correctly, but the *content* is wrong.

## 4. Taxonomy with counts

Primary category (n = 19 failures):

| Primary category | Count | Share |
|---|---|---|
| retrieval-omission | 6 | 31.6% |
| cross-session-contamination | 4 | 21.1% |
| target-attribute-extraction-miss | 3 | 15.8% |
| distractor-entity-binding | 2 | 10.5% |
| polarity-error | 2 | 10.5% |
| immediate-request-vs-enduring-preference | 1 | 5.3% |
| unsupported-answer-specificity | 1 | 5.3% |

Combined primary + secondary mentions (how often a mechanism appears at all):

| Mechanism | Mentions (of 19) |
|---|---|
| retrieval-omission | 11 |
| cross-session-contamination | 8 |
| distractor-entity-binding | 7 |
| target-attribute-extraction-miss | 5 |
| unsupported-answer-specificity | 3 |
| immediate-request-vs-enduring-preference | 2 |
| polarity-error | 2 |

**Reading of the counts.** Two families dominate:

- **Grounding-supply failures (retrieval-omission + cross-session-contamination):
  primary in 10/19, and mentioned in 15/19.** The single supporting session's
  decisive turn is not surfaced into the top-k/trimmed context; topically similar
  *distractor* sessions crowd it out, and the model faithfully answers from the
  wrong session (or fabricates).
- **Answer-side binding/realization failures (target-attribute-miss,
  distractor-entity-binding, polarity, over-narrowing, unsupported specificity):
  primary in 9/19.** Here the decisive fact *was* in context, but the model bound
  the preference to the wrong target, violated a stated negative constraint, or
  over-narrowed / over-specified.

## 5. Illustrative examples (verbatim, trimmed)

**(a) cross-session-contamination — wrong session answered faithfully** `75832dbd`
- Q: "Can you recommend some recent publications or conferences that I might find interesting?"
- GOLD: "…recent research papers, articles, or conferences that focus on artificial intelligence in healthcare, particularly … deep learning for medical image analysis. They would not be interested in general AI topics…"
- MODEL: "…publications or conferences focused on **environmental sustainability, climate change**, and academic research methodology…"
- Evidence: the correct AI-in-healthcare session (`answer_d87a6ef8`) was not surfaced; a distractor session (`2cea94dc`) literally states "User is interested in environmental sustainability and climate change," and the model answered from it.

**(b) distractor-entity-binding — wrong entity name pulled from a distractor** `75f70248`
- Q: "I've been sneezing quite a bit lately. Do you think it might be my living room?"
- GOLD: "…consider the potential impact of their cat, **Luna**, and her shedding … recent deep clean of the living room…"
- MODEL: "…managing cat allergens and dust in the living room, specifically leveraging their existing cat named **Whiskers**…"
- Evidence: both "Luna" and "Whiskers" exist in the corpus; the "Luna" turn was dropped in ranking/trim while the distractor "Whiskers" survived. This is **contamination, not free fabrication** — "Whiskers" is verbatim in the retrieved memory, and the answer prompt explicitly forbids inventing names.

**(c) polarity-error — recommends an explicitly dis-preferred option** `1c0ddc50`
- Q: "Can you suggest some activities I can do during my commute to work?"
- GOLD: "…listening to new podcasts or audiobooks, especially the genre **beyond true crime or self-improvement**, such as history. … would not prefer general podcast topics such as true crime or self-improvement…"
- MODEL: "…listening to history or **self-improvement** podcasts (such as 'Hardcore History' or 'The Mindful Kind')…"
- Evidence: the history-interest turn was surfaced, but the model still folded in "self-improvement," an explicitly excluded genre (pulled from distractor `9345f7dc_1`).

**(d) target-attribute-extraction-miss — decisive comparison ignored despite being in context** `95228167`
- Q: "Any tips on what to look for in a new guitar?"
- GOLD: "…highlight the differences between **Fender Stratocaster and Gibson Les Paul** electric guitars, such as the feel of the neck, weight, and sound profile…"
- MODEL: "…a new guitar that align with their existing Fender Stratocaster and **ukulele**, … the Jack Johnson and Jason Mraz style … **dry climate needs regarding humidity control**…"
- Evidence: the Gibson-Les-Paul-vs-Fender comparison (`answer_5e613445`) was in the prompt, but the model bound to acoustic/ukulele/humidity distractors instead.

**(e) retrieval-omission + fabricated specifics** `06f04340`
- Q: "What should I serve for dinner this weekend with my homegrown ingredients?"
- GOLD: "…incorporate their homegrown **cherry tomatoes and herbs like basil and mint** …"
- MODEL: "…an elegant, impressive, yet easy-to-make dish … specifically **avoiding salmon and favoring options like chicken with lemon** …"
- Evidence: the homegrown-ingredient turn (`answer_92d5f7cd`) was not surfaced (only a stray "basil" from a distractor pasta recipe); the model fabricated an avoid-salmon/favor-chicken profile.

## 6. Pipeline-layer localization

Each failure is localized to the layer(s) where the decisive causal break occurs.
(An item may touch more than one layer.)

| Pipeline layer | Items touching it | Share of 19 |
|---|---|---|
| retrieval-ranking | 12 | 63.2% |
| answer-realization | 10 | 52.6% |
| attribution + target-binding | 5 | 26.3% |
| context-construction (top-k trim) | 5 | 26.3% |
| ingestion / extraction / structured-representation / controller-policy / persistence / judge-scorer | 0 | 0% |

Note on empty layers: no failure was traced to an *ingestion/extraction* miss
(the facts exist in the corpus and, for the answer-side failures, in the prompt),
to *persistence*, or to a *judge-scorer* error strong enough to overturn a verdict.
`structured-representation` is 0 as a per-item *break* but is the systemic *enabler*
(see §7): there is no typed preference object to prioritize during retrieval or to
constrain the answer.

## 7. Root-cause synthesis — the single highest-leverage change

**Diagnosis.** SSP items in LongMemEval-M establish a preference in *one*
supporting session, embedded in many topically similar distractor sessions
(often the same domain with different specifics, sometimes a different persona).
The controller retrieves and ranks *turns* by cosine similarity with no notion of
"this turn is where the user's preference was stated." Consequently the decisive
turn is frequently out-ranked and trimmed away, and the answerer either binds to a
distractor or fabricates. This mechanism is the primary driver in **10/19** and is
present in **15/19** failures. Prompt inspection supplies the causal evidence;
the **0/19 replay repair** is consistent with the diagnosis but cannot isolate
the answer model because replay prompts and contexts differ from v7.

**Highest-leverage fix (single change): make preference grounding first-class and
provenance-constrained.** Represent each stated preference as a typed record
(holder / target / attribute / polarity / scope / source-session) and drive
retrieval to *guarantee* surfacing the supporting-session preference record for
the question's subject, rather than generic per-turn cosine retrieval. This
directly attacks the plurality of failures (the ~15 grounding-supply cases) and
shrinks the distractor-binding secondaries.

**Honest limit of a single change.** Even with perfect grounding, **~9/19** are
answer-side failures (polarity/negative-constraint violations, wrong-target
binding, over-narrowing, unsupported specificity) that persist when the correct
fact is already present. So the grounding fix is necessary but not sufficient; it
must be paired with an **answer contract** (assert only retrieved-and-grounded
preferences; honor stated negatives). See
`SINGLE_SESSION_PREFERENCE_METHOD.md` for the PROPOSED design and ablation matrix
that would attribute credit between the two.

## 8. Caveats (honest)

- **Judge severity / borderline verdicts.** `1da05512` (NAS) is the weakest
  "failure": the model *did* reference the user's external-drive/storage context;
  it was failed for over-specifying security/beginner priorities. Treat it as a
  candidate judge-severity case rather than a clean pipeline defect. No SSP item
  was overturned in adjudication, so we did not relabel it, but it should be
  flagged in any re-adjudication.
- **"Fabrication" is often contamination.** Several judge rationales say the model
  "fabricates" specifics (e.g. `Whiskers`, `Hendrick's`, `lentil curry`), but those
  tokens are verbatim in the retrieved memory. The mechanism is usually
  *distractor binding*, not invention. This distinction matters for the fix:
  tightening decoding alone will not help; retrieval provenance will.
- **Single seed / single run.** Numbers are from one v7 run (seed 0) plus one
  replay; the CI reflects sampling of the 30 items, not run-to-run variance.
- **Primary-vs-secondary is a judgement call** for the mixed cases (e.g.
  `b6025781`, `caf03d32`), where retrieval supplied part of the evidence and the
  answer stage mishandled the rest. The combined-mention counts in §4 are the more
  robust summary than the strict primary split.
- **Attribution of layers is by decisive break**, not by every layer that
  participated; a stricter accounting would also tag `context-construction` on the
  retrieval-omission items where a larger context window might have retained the
  decisive turn.
