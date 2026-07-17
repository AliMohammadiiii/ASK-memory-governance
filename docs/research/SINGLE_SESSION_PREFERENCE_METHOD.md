# Single-Session-Preference (SSP) Correction Method — PROPOSED

> **Status: PROPOSED.** Nothing in this document has been implemented, run, or
> validated. Every schema, contract, retrieval change, ablation arm, and metric
> below is a design grounded in the taxonomy in
> `SINGLE_SESSION_PREFERENCE_FAILURE_ANALYSIS.md` and
> `artifacts/single_session_preference_error_taxonomy.json`. No accuracy claim is
> made for any proposed change. The contaminated v7 diagnostic reference is
> **SSP 11/30**; the incomplete top-up observes 8/29 with one unresolved item
> (maximum 9/30), so no value is transferable across configurations.

## 0. What the taxonomy tells us to fix

From the 19 persistent SSP failures:

- **Grounding supply is the plurality problem** (retrieval-omission +
  cross-session-contamination: primary in 10/19, mentioned in 15/19). The single
  supporting session's preference turn is out-ranked and trimmed away; distractor
  sessions dominate.
- **Answer-side discipline is the second problem** (target/attribute miss,
  distractor-binding, polarity, over-narrowing, unsupported specificity: primary
  in 9/19). Even when the decisive fact is present, the answer binds to the wrong
  target, includes an explicitly dis-preferred option, or over-specifies.

The method therefore has three parts: a **typed preference record** (representation),
**provenance-constrained retrieval** (supply), and an **answer contract** (discipline).

## 1. Typed preference record schema (PROPOSED)

A stated preference becomes a first-class object rather than an unstructured turn.
**A field is included only where the taxonomy shows it does operational work**; the
motivating failure category is named for each. Fields with no operational role in
the observed failures are explicitly excluded (§1.2) to avoid speculative schema.

### 1.1 Included fields

| Field | Purpose | Motivating failure category (from taxonomy) |
|---|---|---|
| `holder` | Whose preference this is (must resolve to the evaluated user, not a distractor persona) | cross-session-contamination (`75832dbd` = a *different persona's* interest was answered); distractor-entity-binding |
| `target` | The entity/subject the preference is about (the hotel, the cat, the guitar comparison, the homegrown ingredients) | target-attribute-extraction-miss (`0edc2aef`, `95228167`, `1a1907b4`); distractor-entity-binding (`75f70248`) |
| `attribute` | The specific dimension preferred on that target (ocean view + rooftop pool; Gibson-vs-Fender neck/weight/sound; turbinado sugar) | target-attribute-extraction-miss (`06f04340`, `95228167`) |
| `polarity` | prefer / avoid — carries stated negatives | polarity-error (`195a1a1b` no phone/TV; `1c0ddc50` not true-crime/self-improvement) |
| `scope` | Breadth and any bounding condition of the preference (broad "special events + food + shows" vs a single event; "evenings before 9:30pm") | immediate-request-vs-enduring-preference (`fca70973` over-narrowing); polarity/`195a1a1b` time-window |
| `stability` | enduring vs one-off / temporary | immediate-request-vs-enduring-preference (`fca70973`); `09d032c9` (an already-owned power bank treated as a fresh purchase) |
| `source_evidence` | **Provenance**: supporting `session_id` + turn index + verbatim span that establishes the record. The linchpin field. | retrieval-omission (all 6), cross-session-contamination (all 4), unsupported-answer-specificity |
| `confidence` | Extractor's confidence; low confidence → keep the preference general / abstain rather than assert specifics | unsupported-answer-specificity (`1da05512`, `caf03d32`); enables the answer contract's abstain rule |

### 1.2 Excluded fields (with reason)

- `strength` — **excluded**. No failure hinged on preference *intensity* (there is
  no `strength-error` occurrence in the taxonomy). Adding it would be speculative.
- `condition` — **excluded as a separate field**. The observed "exceptions" are
  stated negatives ("not phone/TV", "beyond true crime") and are captured by
  `polarity=avoid` on a `target`, plus `scope` for bounding windows. Revisit only
  if genuine conditional preferences (if-X-then-prefer-Y) appear in a larger sample.
- `temporal_scope` — **excluded as a separate field**; the one time-bound case
  (`195a1a1b`, "before 9:30pm") is folded into `scope`, and enduring-vs-temporary is
  carried by `stability`. Split it out only if datedness (as opposed to stability)
  becomes load-bearing.

## 2. Answer contract (PROPOSED)

Goal: stop distractor-binding and fabricated/over-specified answers when they occur
*after* grounding is available (the 9/19 answer-side failures).

1. **Enumerate-then-ground.** Before writing the preference profile, the answerer
   must enumerate candidate preference records for the question's `target`, each
   with its `source_evidence`. Any record whose holder is not the evaluated user or
   whose source is not a retrieved span is dropped.
2. **Assert-only-grounded.** Every specific named in the final answer (brand, pet,
   dish, product, comparison) must trace to a retained record's `source_evidence`.
   If a specific cannot be grounded, the answer must stay general
   ("suggestions that build on the user's stated preferences") — directly targeting
   unsupported-answer-specificity and the "fabrication-that-is-really-contamination"
   pattern (`75f70248` Whiskers, `caf03d32` lentil curry).
3. **Honor negatives.** Any `polarity=avoid` record on the target becomes a hard
   exclusion in the answer — targeting polarity-error (`195a1a1b`, `1c0ddc50`).
4. **Respect scope/stability.** Prefer enduring, broad records over a single
   immediate turn unless the question is explicitly about the immediate item —
   targeting `fca70973`, `09d032c9`.
5. **Abstain gate.** If no user-held, grounded preference record exists for the
   target, answer with the general profile and a low-confidence flag rather than
   inventing one.

## 3. Provenance-constrained retrieval (PROPOSED)

Goal: guarantee the supporting-session preference record reaches the constructed
context (the 15/19 grounding-supply cases; 12/19 touch retrieval-ranking).

- **Preference-record index.** Index typed preference records (from §1), not just
  raw turns, keyed by `target` and `holder`.
- **Subject-anchored guaranteed recall.** Parse the question's subject/target and
  *force-include* the highest-provenance user-held preference record(s) for that
  target into the context (a pinned slot), before generic cosine turns fill the
  remaining budget. This prevents the decisive turn from being trimmed
  (`75f70248` Luna, `6b7dfb22` Instagram/30-day, `32260d93` stand-up-comedy).
- **Holder filter.** Down-weight or exclude preference records whose `holder` is a
  distractor persona, attacking cross-session-contamination (`75832dbd`).
- **Provenance carried into the prompt** so the answer contract (§2) can enforce
  assert-only-grounded.

## 4. Ablation matrix (PROPOSED — not yet executed)

All arms evaluated on the same LongMemEval-M SSP slice (n=30), paired by item.
Point accuracy and CI via `scripts/evaluation/evaluate_single_session_preferences.py`;
paired significance via stratified McNemar vs baseline.

| Arm | Representation (§1) | Provenance retrieval (§3) | Answer contract (§2) | Isolates |
|---|:--:|:--:|:--:|---|
| A. current controller (baseline) | – | – | – | contaminated v7 diagnostic reference = **11/30** |
| B. prompt-only | – | – | wording only | how much is fixable by instruction alone |
| C. provenance-representation-only | yes | – | – | value of typed records with no retrieval change |
| D. provenance-constrained-retrieval-only | yes (index) | yes | – | grounding-supply fix in isolation |
| E. answer-contract-only | – | – | yes | answer discipline on current (often wrong) grounding |
| F. combined | yes | yes | yes | full method |
| G. combined − preference-binding | yes | yes | yes | ablate holder/target binding to size its contribution |

Expected diagnostic reads (hypotheses, not results): D should move the
retrieval-omission / contamination subtypes; E should move polarity and
unsupported-specificity subtypes; the gap between E and F should quantify how much
the answer contract depends on correct grounding; A→G→F isolates the binding step.

## 5. Metrics (PROPOSED)

- **Preference accuracy** — judge-scored SSP accuracy per arm, with stratified
  bootstrap 95% CIs (reuse `evaluate_single_session_preferences.py`) and paired
  McNemar vs baseline.
- **Unsupported-preference rate** — fraction of asserted preference tuples
  (holder/target/attribute/polarity) in the answer that do NOT trace to a retrieved
  `source_evidence` span. Directly scores the assert-only-grounded contract.
- **Cross-person contamination rate** — fraction of answers whose asserted
  preference binds to an entity/persona from a non-supporting session
  (the `75832dbd`/`75f70248` failure mode).
- **Per-subtype breakdown** — accuracy and the two rates above, broken out by the
  taxonomy's primary categories (retrieval-omission, cross-session-contamination,
  target-attribute-extraction-miss, distractor-entity-binding, polarity-error,
  immediate-request-vs-enduring-preference, unsupported-answer-specificity), so each
  arm's credit is attributed to the mechanism it targets.
- **Confidence intervals** — stratified percentile bootstrap on the SSP items
  (n=20000, fixed seed) for every reported rate; paired bootstrap for arm-vs-arm
  differences (mirrors `scripts/build_v8_adjudicated_report.py`).

## 6. Honest scope

- The taxonomy is n=19 failures from a single 30-item SSP slice / one v7 run; the
  schema and ablation are sized to *that* evidence and should be re-checked on a
  larger SSP sample before generalizing.
- `1da05512` is a borderline/judge-severity case (see the analysis doc §8); it
  should not be over-weighted when tuning the answer contract.
- No claim is made that the combined method reaches any particular accuracy. The
  matrix is the instrument to find out; until it is run, all entries except arm A
  are hypotheses.
