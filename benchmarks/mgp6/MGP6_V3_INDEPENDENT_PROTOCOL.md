# MGP-6 v3 independent confirmation protocol

Status: **pre-registered design; not executed**  
Purpose: replace the author-designed MGP-6 v2 pilot with an independently
constructed confirmation set that can test evidence reasoning rather than
scenario-family recognition.

This protocol is deliberately prospective. Nothing in this document upgrades
the scientific status of the existing v2 results.

## 1. Separation of roles

- Freeze the task definition, controller code, prompts, thresholds, cost
  matrices, metrics, and analysis code before any confirmation item is seen.
- A data team that did not design or tune the evaluated controllers writes the
  confirmation items. The controller authors may answer schema questions but
  may not propose, edit, filter, or adjudicate individual test examples.
- Keep the confirmation test labels hidden from controller authors until every
  system has produced a complete, immutable prediction file.
- Record all exclusions before unblinding. Never remove an item because a
  submitted system found it difficult.
- Release role declarations, hashes, timestamps, and a change log with the
  dataset card.

## 2. Construct and sampling frame

The unit of evaluation is a memory transition embedded in a trajectory, not an
isolated template. The sampling frame crosses the following factors:

| Factor | Required levels |
| --- | --- |
| Gold action | KEEP, SUPERSEDE, ABSTAIN |
| Relation | duplicate, elaboration, contradiction, correction, retraction, uncertain conflict |
| Evidence reliability | first-party verified, first-party unverified, delegated source, weak inference, conflicting sources |
| Time | current, explicitly expired, retrospectively corrected, future-scoped, ambiguous |
| Durability | stable profile, temporary state, preference, plan/commitment, derived summary |
| Dialogue structure | direct statement, paraphrase, negation, coreference, delayed evidence, distractor-rich |
| Trajectory pattern | A→B→C, A→B→A, repeated confirmation, branching slot update, delayed retraction |

Each conflict family must contain all three gold actions. No type, conflict label,
source field, lexical cue, or tuple of public metadata may deterministically
identify the action. Families include counterfactual minimal pairs that change
one evidential premise while holding wording and record type as constant as
possible.

At least half of the test set must use trajectories of 5, 10, or 20 turns with
multiple memory slots and delayed evidence. At least one third must be
semi-natural: de-identified, consented dialogue skeletons or scenarios written
from a source distribution independently of the controller specification.

## 3. Split and leakage gates

Partition by writer, source dialogue, trajectory family, and paraphrase family;
none may cross train, development, and confirmation test. Before accepting the
dataset, run these frozen shortcut probes using train+development only:

1. majority class;
2. type-only lookup;
3. conflict-type-only lookup;
4. public-metadata lookup;
5. bag-of-words logistic regression;
6. shallow decision tree;
7. lexical-cue decision list.

The dataset is rejected and regenerated if any non-semantic probe exceeds the
majority baseline by more than 0.10 absolute accuracy on confirmation test, or
if any single public categorical field has normalized information gain above
0.50 with respect to the action. These are construct-validity gates, not
baselines to beat after the fact.

Run exact-duplicate, normalized-string, embedding-neighbour, n-gram, entity,
and author/source overlap audits before unblinding. Publish the audit output.

## 4. Annotation

- Three independent human annotators label every confirmation-test transition;
  at least one annotator is a trained non-expert who did not participate in
  dataset design.
- Annotators are blind to system outputs and proposed controller behavior.
- Collect the gold action, target record(s), resulting active state, lineage
  links, evidence spans, and a short rationale.
- Use a written manual with decision examples that are not copied into the test
  set. Pilot the manual on a separate calibration batch.
- Report raw label distributions, pairwise agreement, Fleiss' kappa, per-class
  agreement, and adjudication rate. Model panels, if used, are reported
  separately and never called human inter-annotator agreement.
- Adjudication is performed by a fourth qualified reviewer or a panel rule
  specified before labels are opened. Preserve all pre-adjudication labels.
- Record informed consent, compensation, redistribution permission, and a
  procedure for removing personal information.

## 5. Frozen systems and component oracles

Evaluate at minimum:

- majority, recency, append-only, and naive-overwrite policies;
- the v2 lexical reference policy without modification;
- the implemented weighted scorecard, if claimed, with weights and thresholds
  frozen on development data;
- a structured LLM policy and an unstructured prompt-matched LLM policy;
- type-only, conflict-only, public-metadata, logistic, tree, and decision-list
  shortcuts;
- a calibrated selective classifier with its abstention threshold selected on
  development data;
- state-of-the-art memory systems through their native observable operations.

Run each controller twice: once with oracle type/relation/evidence fields and
once with predicted fields. This separates extraction, typing, relation,
decision, state-transition, and retrieval failures. Hosted-model systems use
multiple pre-specified seeds or provider snapshots when stochastic variation is
possible.

External systems are not coerced into KEEP/SUPERSEDE/ABSTAIN for the primary
comparison. Report native write, delete, merge, invalidate, no-op, and lineage
observables plus task-level state correctness. Any secondary action mapping is
labelled as a sensitivity analysis with every plausible mapping shown.

## 6. Outcomes and statistical analysis

Primary outcomes on the hidden confirmation test are:

1. action macro-F1;
2. false-commit rate among gold ABSTAIN cases;
3. missed-update rate among gold SUPERSEDE cases;
4. resulting-state exact match and slot-level F1;
5. lineage integrity;
6. expected asymmetric loss under the three frozen cost matrices.

Secondary outcomes are calibration error, Brier score, risk--coverage, per-family
performance, and end-to-end answer/retrieval quality on the clean downstream
track. Report both item-weighted and family-macro estimates.

Use cluster bootstrap with trajectory family as the primary resampling unit and
minimal-pair group as a sensitivity unit. Paired system comparisons resample the
same clusters. Report point estimates, 95% intervals, absolute paired
differences, and exact paired tests where applicable. A zero event count always
receives a finite-sample upper bound. Superiority, equivalence, or
non-inferiority language is allowed only for a pre-specified contrast and margin.
Also report leave-one-family-out performance to expose family dependence.

## 7. Clean downstream track

The downstream track uses one frozen model/judge configuration, all systems on
the same complete sample, no carry-forward of prior successes, no selected
failure replay, and no post-hoc manual patching of the primary score. Persist
per-item requested and actual model IDs, prompts, retries, fallbacks, costs, raw
judgments, and hashes. Raw scores are primary; blinded human adjudication, if
performed, is a separate sensitivity analysis.

Do not include a downstream table in the main paper unless every system passes
the completeness, homogeneity, provenance, and judge-consistency verifier.

## 8. Release gates

The confirmation result is eligible for a main-paper claim only if all gates
pass:

- [ ] controller and analysis freeze predates test access;
- [ ] role separation and conflicts of interest are disclosed;
- [ ] all split-overlap and shortcut thresholds pass;
- [ ] three-human annotation and blinded adjudication are complete;
- [ ] every registered system has complete per-item predictions;
- [ ] component-oracle and predicted-component runs are present;
- [ ] cluster-aware estimates and cost-sensitive outcomes are generated by code;
- [ ] external systems use native metrics in the primary comparison;
- [ ] downstream evidence, if claimed, passes the homogeneous-run verifier;
- [ ] dataset, code, model/provider versions, hashes, and exclusions are archived.

If any gate fails, the result remains diagnostic and the failure is reported;
missing evidence is never imputed.
