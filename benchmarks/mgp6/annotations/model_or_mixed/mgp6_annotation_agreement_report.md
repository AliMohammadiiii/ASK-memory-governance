# MGP-6 v2, Multi-Model Annotation Agreement Report

## Scope

This report compares four independent model-produced annotation files against the existing author gold labels on the 90-item MGP-6 v2 test split. These are **model annotators, not human annotators**; therefore the results are best described as a multi-model annotation audit and do not by themselves establish human inter-annotator agreement.

## Data integrity

- 90/90 test scenarios present in every annotation file.
- No missing scenario IDs.
- No duplicate scenario IDs.
- All actions valid (`KEEP`, `SUPERSEDE`, `ABSTAIN`).
- All confidence values valid in `[0,1]`.

## Per-annotator agreement with author gold

| Annotator | Raw agreement | Cohen's κ | 95% bootstrap CI | Macro-F1 | Errors |
|---|---:|---:|---:|---:|---:|
| Gemini Pro | 100.0% | 1.0000 | [1.0000, 1.0000] | 1.0000 | 0 |
| GPT Sol High | 97.8% | 0.9630 | [0.9046, 1.0000] | 0.9826 | 2 |
| Kimi | 100.0% | 1.0000 | [1.0000, 1.0000] | 1.0000 | 0 |
| Z | 100.0% | 1.0000 | [1.0000, 1.0000] | 1.0000 | 0 |

## Multi-annotator agreement across the four model annotators

- Fleiss' κ: **0.9815**, 95% bootstrap CI **[0.9520, 1.0000]**.
- Krippendorff's α (nominal): **0.9815**, 95% bootstrap CI **[0.9520, 1.0000]**.
- Unanimous 4/4 agreement: **88/90 (97.8%)**.
- 3–1 majority cases: **2/90 (2.2%)**.
- 2–2 ties: **0**.
- Majority-vote consensus agreement with author gold: **90/90 (100.0%)**.

## Pairwise agreement

| Annotator A | Annotator B | Raw agreement | Cohen's κ | 95% bootstrap CI |
|---|---|---:|---:|---:|
| Gemini Pro | GPT Sol High | 97.8% | 0.9630 | [0.9044, 1.0000] |
| Gemini Pro | Kimi | 100.0% | 1.0000 | [1.0000, 1.0000] |
| Gemini Pro | Z | 100.0% | 1.0000 | [1.0000, 1.0000] |
| GPT Sol High | Kimi | 97.8% | 0.9630 | [0.9044, 1.0000] |
| GPT Sol High | Z | 97.8% | 0.9630 | [0.9044, 1.0000] |
| Kimi | Z | 100.0% | 1.0000 | [1.0000, 1.0000] |

## Per-type agreement with author gold

| Type | Gemini Pro | GPT Sol High | Kimi | Z |
|---|---:|---:|---:|---:|
| T1 | 100.0% | 93.3% | 100.0% | 100.0% |
| T2 | 100.0% | 93.3% | 100.0% | 100.0% |
| T3 | 100.0% | 100.0% | 100.0% | 100.0% |
| T4 | 100.0% | 100.0% | 100.0% | 100.0% |
| T5 | 100.0% | 100.0% | 100.0% | 100.0% |
| T6 | 100.0% | 100.0% | 100.0% | 100.0% |

## Disagreement cases requiring adjudication

### MGP6V2-T1-TEST-017
- Author gold: **SUPERSEDE**
- Perturbation: `Fruit based breakfasts have become my weekday routine.`
- Gemini Pro: **SUPERSEDE** (confidence 0.98), The user asserts that fruit-based breakfasts are now their weekday routine. This durable change in habit replaces the prior preference for savory breakfasts.
- GPT Sol High: **ABSTAIN** (confidence 0.74), The user reports a weekday breakfast routine rather than a general breakfast preference. A fruit-based weekday habit can coexist with an overall savory preference, so a same-slot replacement is not sufficiently established.
- Kimi: **SUPERSEDE** (confidence 0.95), The user's later statement reliably establishes a new durable standing value for the same memory dimension, implicitly invalidating the prior value.
- Z: **SUPERSEDE** (confidence 0.95), The user states fruit based breakfasts have become their weekday routine, a durable same-slot claim that supersedes the prior savory preference.
- Adjudication note: the key question is whether a **weekday routine** necessarily occupies the same mutually exclusive slot as the broader `breakfast_style_preference`. The 3–1 majority supports `SUPERSEDE`, but the dissent identifies a plausible scope mismatch.

### MGP6V2-T2-TEST-016
- Author gold: **SUPERSEDE**
- Perturbation: `The renewal notice for my subscription is dated the 20th.`
- Gemini Pro: **SUPERSEDE** (confidence 0.95), The user shares new, specific evidence from a renewal notice that places the subscription renewal on the 20th. This updates and replaces the previously held date.
- GPT Sol High: **ABSTAIN** (confidence 0.96), The date printed on a renewal notice is not necessarily the subscription's renewal day. The event therefore does not clearly update the same semantic fact as the stored 18th renewal day.
- Kimi: **SUPERSEDE** (confidence 0.95), The user's later statement reliably provides updated factual information for the same episodic memory slot, establishing the new value as current.
- Z: **SUPERSEDE** (confidence 0.93), The user reports the renewal notice for their subscription is dated the 20th, a reliable same-slot durable claim that supersedes the prior 18th value.
- Adjudication note: the phrase **“renewal notice … is dated the 20th”** may refer to the notice's document date rather than the subscription renewal day. This is a substantive same-slot ambiguity and should be manually reviewed or the item wording clarified.

## Recommended paper interpretation

The four-model audit shows extremely high consistency with the existing labels, but it should not be reported as human inter-annotator agreement. For a paper, report it as an **LLM-based multi-model annotation audit** if retained. To satisfy the stronger claim in the runbook-independent annotation with Cohen's κ as a human reliability check-obtain at least one blinded human annotation pass over the 90 test items and then compute human-vs-author κ and adjudicate disagreements.

The two identified disagreement cases are useful quality-control findings. They should be adjudicated before freezing the final gold labels, because both dissent rationales concern semantic scope or referent identity rather than arbitrary model error.
