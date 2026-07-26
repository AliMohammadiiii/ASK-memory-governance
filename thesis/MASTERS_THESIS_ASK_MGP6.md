# Auditable Governance of Long-Term Memory in Language Agents

## The ASK Controller (Keep–Supersede–Abstain), the MGP-6 v2 Diagnostic, and Evidence-Bounded Evaluation

**Master's Thesis — English Review Draft**
Administrative fields (candidate, supervisor, advisor, faculty, dates, signatures) are intentionally left as placeholders and are consolidated in `frontmatter/ADMINISTRATIVE_PLACEHOLDERS.md`. They must never be filled in by tooling.

Persian-language front matter is available in `frontmatter/abstract_fa.md`, `frontmatter/extended_summary_fa.md`, and `frontmatter/terminology_fa.md`.

> **Evidence-status notice.** Every number in this thesis is transcribed from the frozen evidence ledger `artifacts/results_ledger.json` v1.1 (sha256 `fea886f1ae746e921e785536e6ce47bea89ec11b99f8f2e75936dc71c6c5185e`, created 2026-07-13) or the later construct-validity audit `artifacts/analysis/mgp6_validity_audit.json`. The 2026-07-15 shortcut failure supersedes the ledger's older `final_candidate` interpretation for MGP-6 v2: those policy rows are now diagnostic. No `failure_replay_only`, `incomplete`, `invalid`, `externally_pending`, or mapping-dependent row is used as a primary capability result. Conversion to the official University of Tehran thesis template and completion of its administrative fields remain external requirements (see `thesis/README.md` and `thesis/thesis_checklist.md`).

---

## Declaration

This manuscript distinguishes verified results, supported-with-caveat results, diagnostic observations, and hypothesized designs, following the strength tags of `reports/CLAIMS_EVIDENCE_MATRIX.md`. Invalid and superseded runs are named and excluded (`docs/audit/INVALID_AND_SUPERSEDED_RUNS.md`). Raw and adjudicated numbers are always reported together. No LongMemEval number is presented as final.

## Abstract

Long-term memory makes language agents more useful and, at the same time, creates a governance problem: the agent must decide what to keep, what to supersede when new evidence contradicts stored state, and when to abstain because the evidence is insufficient to justify a write. These write-time decisions are not the same construct as downstream answer accuracy, and evaluations that collapse them conceal both capability and risk.

This thesis formulates memory governance as an explicit, auditable three-way decision — KEEP, SUPERSEDE, ABSTAIN — over typed, provenance-tracked records and separates evaluation of the write action, resulting state/lineage, and later answer. It exercises the framework on MGP-6 v2, an author-designed 180-item pilot. The most important result is a failed construct-validity gate: conflict type alone deterministically identifies the action, and a conflict-type-only lookup fitted on train and development reaches 1.000 held-out test accuracy (type-only: 0.9667). Consequently, the pilot cannot isolate evidence reasoning from scenario recognition and supports diagnostic mechanism observations rather than method-generalization claims.

On the 90-item test split, the transparent lexical reference policy reaches 0.8889 accuracy / 0.9145 macro-F1, while the structured LLM policy reaches 0.9000 / 0.9040. Their paired template-family cluster interval includes zero. The reference policy makes 0/33 observed action false commits, but the one-sided 95% upper bound is 0.0868 and it misses 10/45 required updates. Frozen cost matrices reverse the preferred system between commit-averse and update-responsive regimes. Full-corpus ablations remain useful only as within-generator mechanism checks: notably, removing lineage leaves action accuracy unchanged while lineage integrity falls 0.8556→0.3689.

One independent human re-annotation and a separate four-model panel are reported without describing them as multi-human agreement. Mapped external-system rankings, the incomplete six-shot run, and all existing LongMemEval results are excluded from primary capability claims. The thesis contributes an auditable evaluation decomposition, released per-item predictions and cluster-aware analysis, and a prospective independently generated, multi-human, trajectory-level confirmation protocol. It does not establish controller superiority, population safety, calibrated confidence, or long-lived deployment performance.

**Keywords:** long-term memory, language agents, memory governance, supersession, abstention, provenance, lineage, auditability, diagnostic evaluation, selective prediction, MGP-6, ASK Controller, LongMemEval.

## Acknowledgements

Institutional and personal acknowledgements are administrative front matter and will be added from `frontmatter/ADMINISTRATIVE_PLACEHOLDERS.md` before submission. The technical package acknowledges the LongMemEval authors [@wu2025longmemeval], the maintainers of the evaluated external memory systems, and the annotation panel configuration documented in the ledger.

## Reader's guide

Chapter 1 frames the research problem and questions. Chapter 2 situates the work in agent memory systems, memory lifecycle research, benchmarks, belief revision, and selective prediction, including the 2026 near neighbors. Chapter 3 formalizes the problem and threat model. Chapter 4 specifies the ASK Controller as implemented. Chapter 5 documents MGP-6 v2 and its annotation evidence. Chapter 6 defines the experimental methodology and the claim-eligibility policy. Chapter 7 reports results. Chapter 8 gives the error analysis and discussion. Chapter 9 addresses validity, ethics, and limitations. Chapter 10 concludes. Appendices A–F provide schemas, prompt pointers, metric definitions, the annotation-manual pointer, reproducibility commands, and the artifact manifest.

## Abbreviations

| Term | Meaning |
|---|---|
| ASK | Keep–Supersede–Abstain: the three-action memory-governance controller of this thesis |
| MGP-6 v2 | Author-designed six-type memory-governance diagnostic slice (180 scenarios) |
| LME-M | Stratified 180-item LongMemEval-M evaluation slice (6 competencies × 30, seed 0) |
| SSP | Single-session preference (LongMemEval competency) |
| RD | Paired risk difference (accuracy difference on the same items) |
| CI | Confidence interval |
| IAA | Inter-annotator agreement (not claimed here; see §5.5) |
| n.s. | Not statistically significant |
| JSONL | JSON Lines format |


# 1. Introduction and Research Questions

## 1.1 Motivation

A language model with no persistent memory cannot reliably carry preferences, commitments, or corrections across sessions. A language model with persistent memory is risky for the opposite reason: stale facts can keep influencing behavior after the user has corrected them, contradictory records can accumulate silently, and a system can act on information it should have refused to write in the first place. The engineering objective is therefore not "remember as much as possible" but to govern the memory write as a decision under explicit policy.

This observation changes where control must live. Prompting a model to "be careful" is insufficient because memory writes have side effects that outlive the prompt. A new candidate fact must be classified against the existing store — is it independent, a duplicate, or a contradiction of a prior record? — and the resulting action must be explicit and auditable: keep the new record alongside the old, supersede the old record while preserving its lineage, or abstain because the evidence is too ambiguous to commit either way. When a system cannot express the third option, every conflict becomes a silent overwrite or a silent duplicate.

Existing evaluations mostly treat memory as an answer-retrieval problem: given a long interaction history, can the model answer a later question [@wu2025longmemeval; @maharana2024locomo]? That view is valuable but incomplete: end-to-end question accuracy cannot attribute a failure to the write decision that caused it, and it cannot see governance failures that happen not to affect the sampled questions. A governance evaluation must score the decision boundary itself.

## 1.2 Research problem

> How can a language-agent memory system make and audit policy-sensitive write decisions — keep, supersede, abstain — and how can those decisions be evaluated without conflating governance correctness with retrieval or answer quality?

The problem decomposes into five concerns: **representation** (typed memory records with provenance and lineage), **decision** (an interpretable, abstention-aware action policy), **execution** (supersession must actually mark the prior record inactive and preserve its lineage), **measurement** (decision-level metrics with correct denominators, plus state metrics such as lineage integrity and stale retrieval, distinct from answer metrics), and **honest reporting** (every number carries a claim-eligibility label; contaminated or patched runs are labeled as such).

## 1.3 Research questions

**RQ1 — Architecture.** What controller decomposition makes memory-write decisions explicit, interpretable, and auditable, and prevents a language model from mutating memory outside a governed action vocabulary?

**RQ2 — Diagnostic.** Can a compact, author-designed diagnostic slice expose memory-governance failures — invalid commits, premise acceptance, lineage loss — that are invisible to downstream answer accuracy?

**RQ3 — Measurement.** Which metrics separate decision correctness, memory-state correctness, and downstream answer behavior, and which shipped metrics fail (and must be disclosed as failing)?

**RQ4 — Reliability.** How far do the reported conclusions survive paired significance testing with multiplicity control, annotation audit, and adversarial review of run provenance?

**RQ5 — Reproducibility.** What artifact and claim controls keep a thesis, its papers, and its code mutually consistent — including when the honest answer is "this number is not final"?

## 1.4 Hypotheses and their outcomes (preview)

The original directional comparisons are not confirmatory because the pilot fails its shortcut gate. Chapter 7 therefore treats them as diagnostics and reports these outcomes:

- **H1 — Governance framing helps an LLM.** Not identified by v2: structured and unstructured prompts differ on a label-leaking collection, so the observed gap is descriptive.
- **H2 — An interpretable reference policy can match an LLM policy.** No superiority or non-inferiority conclusion: test accuracy is 0.8889 versus 0.9000 and the family-clustered paired interval includes zero.
- **H3 — Abstention is load-bearing for action safety.** Mechanistically supported inside the generator, but not validated externally; zero observed action false commits has a non-zero finite-sample upper bound and accompanies missed updates.
- **H4 — Decision and stored-state metrics can diverge.** Supported as a measurement demonstration: the no-lineage ablation preserves action accuracy while degrading lineage integrity.
- **H5 — Controller end-task superiority on LongMemEval.** Not supported; existing downstream runs are contaminated, incomplete, or selection-biased.

## 1.5 Contributions

1. **Formulation and evaluation decomposition (RQ1, RQ3).** Memory writes are represented as KEEP/SUPERSEDE/ABSTAIN decisions over typed, provenance-tracked, lineage-preserving records and evaluated separately at action, state, and answer layers.
2. **Construct-validity audit (RQ2, RQ4).** Reproducible type/conflict/metadata shortcuts, family and minimal-pair cluster bootstrap, calibration diagnostics, risk–coverage, and asymmetric expected-cost analysis expose the limits of MGP-6 v2.
3. **Measured negative result (RQ4).** The held-out reference policy does not outperform the structured LLM, and its zero observed action false commits trade against missed updates; the thesis reports the null and cost sensitivity directly.
4. **Mechanism diagnostics (RQ2, RQ3).** Full-corpus ablations show how action and lineage metrics can disagree, without treating author-aligned ablations as independent validation.
5. **Evidence exclusion and successor design (RQ4, RQ5).** Incomplete, mapped, contaminated, and selection-biased results are excluded from primary claims; a role-separated v3 protocol specifies independent generation, three-human annotation, long trajectories, hidden test labels, native external metrics, and cluster-aware analysis.
6. **Reproducible evidence package (RQ5).** Released per-item predictions, audit JSON/Markdown, bibliography checks, a claim-evidence matrix, and machine-readable ledgers keep the paper, thesis, code, and limitations synchronized.

## 1.6 Scope

The thesis evaluates the ASK formulation on an author-designed diagnostic slice and one stratified LongMemEval-M slice with a single base model family and single seed. It does not claim community-benchmark status for MGP-6 v2, does not claim end-task superiority on LongMemEval, does not claim human multi-annotator agreement, and does not claim that governance on these slices generalizes to open-domain deployments. These boundaries are stated because they are what the evidence supports; Chapter 9 enumerates them systematically.

## 1.7 Thesis structure and contribution map

| Research question | Main chapter(s) | Primary artifact |
|---|---|---|
| RQ1 | Chapter 4 | `src/ask/` (policy, memory operations, orchestrator) |
| RQ2 | Chapters 5, 7 | `benchmarks/mgp6/` (data, manual, metrics), ablation runs |
| RQ3 | Chapters 6, 7 | `metrics_mgp6.py`, ledger `known_metric_issues` |
| RQ4 | Chapters 7, 8, 9 | `reports/STATISTICAL_ANALYSIS.md`, `reports/ERROR_TAXONOMY.md`, `reports/THREATS_TO_VALIDITY.md` |
| RQ5 | Chapters 6, 9, App. E–F | `artifacts/results_ledger.json`, `reports/CLAIMS_EVIDENCE_MATRIX.md` |


# 2. Background and Related Work

This chapter follows the verified related-work audit, with submission citations rechecked against primary metadata sources on 2026-07-15. The most important change relative to earlier drafts is a cluster of near neighbors — STALE, TOKI, Supersede, MemGuard, and HaluMem — that are conceptually closer to ASK than the production systems archived in Chapter 7 and constrain which novelty claims remain defensible (§2.8).

## 2.1 Memory in language-agent systems

*Memory* covers several mechanisms with different mutability and deletion semantics: context-window memory, retrieval memory, summary memory, structured records, and model parameters. Long context does not remove governance obligations — long-context models use evidence unevenly by position [@liu2024lost] — and retrieval-augmented generation separates storage from generation without providing a write policy [@lewis2020retrieval; @borgeaud2022improving].

The systems line most relevant to ASK treats memory as an agent-managed store. MemGPT frames the LLM as an operating system that self-edits tiered memory [@packer2023memgpt]; its open-source successor Letta is evaluated in Chapter 7 (0.678 action accuracy under the favourable NOOP→ABSTAIN mapping). MemGPT's memory edits are opaque function calls: there are no write-time decision criteria, no abstention, no lineage. Mem0 productionizes an extract–consolidate–retrieve pipeline whose LLM chooses ADD/UPDATE/DELETE/NOOP per item [@chhikara2025mem0]; its NOOP means "nothing new", not "too ambiguous to commit", and it exposes no supersession lineage (Chapter 7: 0.622 upper bound, invalid-commit rate 1.0). Zep/Graphiti stores a bi-temporal knowledge graph in which contradicted edges receive invalidation timestamps instead of deletion [@rasmussen2025zep] — the strongest shipped precedent for supersession-with-history — but invalidation is a side effect of LLM extraction, not a governed decision with an abstain option, and Zep never scores whether an invalidation was correct. MemOS proposes MemCube versioning/provenance and uses the word "governance" [@li2025memos], but publishes no decision rule for supersede-vs-keep-vs-refuse; through its adapter, supersession is not even observable (Chapter 7: bound-only). A-MEM evolves Zettelkasten-style notes but always integrates new information [@xu2025amem]; MemoryBank forgets on an Ebbinghaus schedule — time-driven, not evidence-driven [@zhong2024memorybank]; Generative Agents accumulate an append-only stream with reflection [@park2023generative].

Two recent lines are closer to ASK's decision framing. Memory-R1 trains an RL memory manager over a discrete ADD/UPDATE/DELETE/NOOP action space [@yan2025memoryr1] — the clearest prior formalization of writes as actions — but the policy is opaque (PPO/GRPO), the reward is answer-level, and NOOP is not uncertainty-driven abstention. RMM performs prospective merge-or-add at session end with retrospective RL-refined retrieval [@tan2025rmm]; its merge-vs-add echoes supersede-vs-keep but uses similarity thresholds without contradiction semantics or abstention. MemGuard assigns each memory an explicit functional role (type) at write time to prevent cross-type contamination [@ha2026memguard]; ASK's no-typing ablation (macro-F1 0.9399→0.5680, KEEP F1→0.0) makes the same argument experimentally.

## 2.2 Memory lifecycle, revision, and conflict

FadeMem classifies new-vs-old memory pairs (compatible / contradictory / subsumes / subsumed) and applies decay or fusion [@fademem2026]; it always acts on a detected conflict — there is no abstain — and suppresses rather than preserving lineage. PAMU updates preference signals only when drift is significant, via sliding-window and EMA fusion [@sun2025pamu]: a conservative, interpretable update trigger, but for preference vectors only, with no discrete action space. TOKI is the closest conceptual neighbor found in the verified audit [@wang2026toki]: it argues that contradiction resolution *is* write-time concurrency control, types four production heuristics as bitemporal operators, and preserves the losing fact in an audit row. Its await-confirmation operator is a formal ancestor of ABSTAIN and its audit row parallels supersession lineage. Reddy and Challaram's deterministic conflict-resolution result [@reddy2026freshness] motivates testing interpretable update logic on independent data; it does not validate the author-designed MGP-6 pilot by analogy.

## 2.3 Benchmarks and evaluation for agent memory

LongMemEval evaluates chat assistants on five long-term memory abilities including knowledge updates and abstention [@wu2025longmemeval]; it is this thesis's downstream substrate (a stratified 180-item slice), and it is end-to-end only — it cannot attribute failure to the write decision. LoCoMo tests very long conversational memory at scale [@maharana2024locomo]. HaluMem separately scores extraction, updating, and QA and reports that hallucinations accumulate at extraction/update [@halumem2025]; it detects hallucination rather than scoring a governed action choice, and it does not use gold KEEP/SUPERSEDE/ABSTAIN actions or lineage and premise-resistance metrics. The contribution here is therefore the operationalization and controlled, layered evaluation of this particular policy combination, not a claim of primacy for operation-level evaluation or decision typologies.

STALE is a high-priority benchmark neighbor [@chao2026stale]: 400 expert-validated implicit-conflict scenarios probing State Resolution, Premise Resistance, and Implicit Policy Adaptation. It shares MGP-6's constructs almost by name (MGP-6's query modes include `premise_resistance`; its single annotation disagreement is an `implicit_conflict` item). The decisive difference is scope: STALE probes a frozen agent's *read-side* recognition that its memory is stale, whereas MGP-6 scores *write-time actions* with an abstain option, supersession lineage, and memory-state metrics. Supersede isolates the "supersession gap" on the LongMemEval knowledge-update subset and trains it with GRPO [@patel2026supersede]; its reward is answer-time fact currency rather than a write-action taxonomy with abstention, lineage, or an interpretable policy. GateMem uses the phrase "memory governance" for a different axis — access control, deletion compliance, and utility across principals in shared memory pools [@ren2026gatemem]. RSCB-MC applies risk-sensitive contextual bandits with explicit abstention to memory *retrieval* in coding agents [@iscan2026remember]. Together these verified neighbors preclude any primacy claim for abstention, governance, update control, provenance, or operation-level measurement.

Benchmark and dataset documentation follows the spirit of datasheets and model cards [@gebru2021datasheets; @mitchell2019modelcards]; the agreement statistics of Chapter 5 use Cohen's κ [@cohen1960coefficient], and the interval estimates of Chapters 5–7 use bootstrap methods [@efron1993bootstrap].

## 2.4 Belief revision and knowledge editing

The AGM theory of belief change — expansion, revision, contraction under minimal-change postulates — is the formal ancestor of KEEP/SUPERSEDE [@alchourron1985theory]; classical AGM has no native abstain (non-prioritized revision covers declining input). ASK is best read as an operational, resource-bounded approximation of non-prioritized revision for LLM memory; no formal AGM compliance is claimed or proven. Parametric knowledge editing (ROME, MEMIT) evaluates edits in weight space with efficacy/generalization/specificity [@meng2022rome; @meng2023memit] — the decision-level-evaluation analogue for parameters; editing assumes the edit should happen, whereas ASK governs *whether* to commit at all.

## 2.5 Selective prediction and abstention

Abstention descends from the reject option [@chow1970reject], selective classification [@elyaniv2010selective; @geifman2017selective], and learning to defer [@madras2018predict; @mozannar2020consistent]. ASK applies that established idea at memory-write time. TOKI's await-confirmation and RSCB-MC's retrieval-time abstention further narrow the contribution. The defensible result is a within-generator mechanism signature plus explicit false-commit/missed-update trade-off, not a general safety effect.

## 2.6 Personalization and preference modeling

PrefEval shows preference following collapses within about ten turns zero-shot [@zhao2025prefeval] — external motivation for the single-session-preference failure line in Chapter 8, with the difference that PrefEval measures following while this thesis attributes failure mechanism (grounding supply vs answer-side discipline). PersonaMem benchmarks dynamic user profiling across sessions with frontier models around 50% [@jiang2025personamem]; LaMP is the canonical retrieval-augmented personalization suite with static profiles [@salemi2023lamp].

## 2.7 Provenance and auditability

Provenance *storage* is well-precedented: Zep's bi-temporal validity intervals and episodes [@rasmussen2025zep], TOKI's audit rows [@wang2026toki], MemOS's MemCube metadata [@li2025memos], and HaluMem's evaluation-side error tracing [@halumem2025]. Auditability as a governance requirement also appears in alignment and risk frameworks [@ouyang2022training; @bai2022constitutional; @nist2023airmf]. ASK scores provenance and lineage ablations inside its pilot; the no-lineage result demonstrates that action accuracy can miss lineage degradation, but author alignment prevents a general causal claim.

## 2.8 Positioning and allowed novelty claims

Following `reports/NOVELTY_CLAIMS_ALLOWED.md` and the verified audit, the thesis makes one narrow contribution claim: it **operationalizes and evaluates the combination** of an interpretable KEEP/SUPERSEDE/ABSTAIN write policy, typed and provenance-tracked records, lineage-preserving transitions, and separate decision-, stored-state/lineage-, and downstream-answer measurements. The controlled ablations attribute distinct failure signatures to components of that combination. The thesis does not claim invention or primacy for write operations as actions, update/versioning, provenance, lineage, abstention, write gating, operation-level evaluation, or the term "memory governance".


# 3. Problem Formulation

## 3.1 System boundary

Let an interaction stream produce candidate memory items. At step \(t\), extraction yields a candidate \(c_t\) (typed content with provenance), the store state is \(M_t\) (a set of typed records, each active or superseded, with lineage links), and the controller computes a relation \(r_t \in \{\text{independent}, \text{duplicate}, \text{update/contradiction}, \text{unclear}\}\) between \(c_t\) and a selected prior record, then a decision

\[
d_t = \pi(c_t, r_t, M_t) \in \{\text{KEEP}, \text{SUPERSEDE}, \text{ABSTAIN}\},
\]

with transition semantics

- **KEEP**: insert \(c_t\) as a new active record (also the correct action when no conflicting prior exists);
- **SUPERSEDE**: insert \(c_t\), mark the conflicting prior inactive, and record a lineage link from the new record to the superseded one;
- **ABSTAIN**: no mutation; the conflict or ambiguity is recorded for review rather than committed.

Retrieval reads only active records; lineage remains queryable for audit and for explicitly historical questions. The policy \(\pi\) may be a deterministic scorecard (§4.4) or an LLM (§4.5); in both cases the action vocabulary and the transition semantics are fixed by code, not by the model.

## 3.2 What makes a write decision wrong

Three governance failure modes are scored separately (formal definitions in Appendix C):

1. **Invalid commit** — committing a write (KEEP or SUPERSEDE) on an item whose gold action is ABSTAIN: the store now contains a record that policy says should not have been committed.
2. **Missed supersession** — choosing KEEP or ABSTAIN when the gold action is SUPERSEDE: the stale record remains active. Its conservative sub-case, SUPERSEDE→ABSTAIN, leaves the store consistent-but-stale without committing anything false; the harmful sub-case, silent KEEP, leaves an unresolved contradiction active.
3. **Lineage loss** — performing the right action while failing to preserve the supersession chain, invisible to action accuracy but fatal to auditability.

Downstream, two state-dependent behaviors are scored: **stale retrieval** (a superseded record surfaces as current) and **premise resistance** (whether the system rejects a query premise that its governed memory contradicts).

## 3.3 Functional requirements

- **FR-1 Typed extraction.** Candidate memories carry a type (e.g., stable preference, transient preference, episodic fact), holder/subject, and source provenance.
- **FR-2 Relation classification.** Each candidate is classified against retrieved priors before any write.
- **FR-3 Three-action decision.** Every write decision is one of KEEP/SUPERSEDE/ABSTAIN; unknown or unparsable proposals resolve to no mutation.
- **FR-4 Lineage preservation.** SUPERSEDE links the new record to the superseded one; superseded records are excluded from ordinary retrieval but never silently destroyed.
- **FR-5 Interpretable policy option.** A deterministic, feature-scored policy must be available so decisions can be explained and audited without model introspection.
- **FR-6 Decision export.** Per-item decisions, features, and outcomes are exported with stable IDs for scoring.
- **FR-7 Evidence-labeled reporting.** Every reported metric carries the run's claim-eligibility label.

## 3.4 Invariants

1. No memory mutation outside the three-action vocabulary.
2. No SUPERSEDE without an identified prior record; lineage recorded atomically with the write.
3. ABSTAIN never mutates state.
4. Retrieval of active records never returns superseded ones (violations are scored as stale retrieval, not patched).
5. No unparsable model output is coerced into a write.
6. No result enters a manuscript table without a ledger entry and eligibility label.

## 3.5 Threat model and failure sources

Accidental and adversarial sources considered: ambiguous or contradictory user statements; model hallucination of relations or targets; distractor content crowding out decisive evidence at retrieval time; provider failures corrupting extraction (empirically observed: HTTP-402 no-responses cached as empty extractions in the v7 LongMemEval run, §7.6); judge errors in downstream grading (empirically observed: number-word/date false negatives, §8.3); and researcher degrees of freedom (fix-on-failure loops without confirmation sets — the reason the LongMemEval failure replay is excluded from final claims, §9.1). Chapter 9 maps each to a validity threat with mitigation status.

## 3.6 Failure taxonomy by causal layer

| Layer | Example failure | Primary diagnostic |
|---|---|---|
| Extraction | candidate fact missed or fabricated | extraction traces; fail-closed policy (v8) |
| Relation classification | contradiction labeled independent | relation confusion; escalation gating |
| Decision | KEEP chosen where gold is SUPERSEDE | action confusion matrix; per-action F1 |
| Commit safety | write on a gold-ABSTAIN item | invalid-commit rate |
| Lineage | supersession chain broken | lineage integrity |
| Retrieval | superseded record surfaces; decisive turn trimmed away | stale-retrieval rate; SSP taxonomy (§8.1) |
| Answer | correct grounding present, wrong binding | answer-side categories of the SSP taxonomy |
| Judge | correct answer graded wrong | adjudication ledger; κ between judges |


# 4. ASK Architecture and Implementation

All code anchors below refer to the canonical repository (`src/ask/…`) and were verified in the pipeline reconstruction audit (`docs/audit/CONTROLLERRUN_RECONSTRUCTION.md`).

## 4.1 Architectural overview

The controller surrounds a SQLite-backed memory store with a governed write path: per-turn extraction of typed candidates, relation classification against retrieved priors, a scored three-action policy, transition execution with lineage, and retrieval/answer stages that consume only governed state. The per-session flow is driven by `ControllerOrchestrator.answer()` (`src/ask/pipeline/orchestrator.py`).

![ASK Controller architecture.](../docs/figures/figure_07_ask_controller_architecture.png)

```text
User turns
   |
   v
[Extractor (strict JSON schema)] --> typed candidate memories
   |
   v
[Prefilter: top-64 turns by question similarity]
   |
   v
[Relation classifier (two-stage, optional escalation)]
   |            candidate vs selected prior
   v
[Policy: scored KEEP / SUPERSEDE / ABSTAIN]
   |
   v
[Memory operations: insert_active | supersede(+lineage) | no-op]
   |
   v
[Retrieval over active records (dense, k=16, neighbor expansion)]
   |
   v
[Answer-context compilation (session-diverse rerank, ~12k-token budget)]
   |
   v
[Answerer]  -->  [Judge / grader with guarded normalization]
```

## 4.2 Extraction

`Extractor.render_prompt()` renders a per-turn extraction prompt bound to a strict JSON schema (`ExtractionOutput.model_json_schema()`); `Extractor.extract()` is called per user turn, concurrently (default concurrency 8). Extraction is fail-closed as of v8: on a provider no-response the extractor raises rather than caching a fabricated empty extraction — the v7 behavior of caching empties is the documented contamination source F1/F2 (§7.6). A content-keyed shared extraction cache allows cross-run reuse without re-introducing synthetic empties.

## 4.3 Relation classification and prior selection

For each candidate, `_process_candidate()` runs a two-stage relation classifier (`RelationClassifier.classify()`) with an optional cascade escalation to a stronger model — gated so that escalation is a no-op unless a genuinely different model is configured (the v7 run set `BIG_MODEL == FAST_MODEL`, making its escalation tier inert; disclosed in §7.6). Prior selection (`_find_prior`, `_select_prior_relation`) picks the stored record against which the relation is evaluated.

## 4.4 Prototype scorecard and released reference policy

`controller.policy.decide()` implements the scored three-action rule:

```text
if S_abstain  > θ_abs:                          ABSTAIN
elif S_revise > θ_sup and relation_update > 0:  SUPERSEDE
else:                                           KEEP
```

with feature scoring in `src/ask/controller/scoring.py`. The features are deliberately few and human-legible (a five-feature scorecard over relation evidence, type compatibility, provenance agreement, and conflict signals), so a runtime decision can be explained by inspection of its feature values.

This runtime scorecard did **not** generate the released MGP-6 reference predictions. Those predictions came from the deterministic lexical predicate policy in `benchmarks/mgp6/systems/policies.py`. Chapter 7 therefore evaluates that artifact as a *reference policy*, not as evidence for the five-feature scorecard or its thresholds. The scorecard remains an implemented architectural option whose independent tuning and evaluation are open work.

## 4.5 The LLM policy and the decision baselines

The LLM-backed controller replaces the scorecard with a model decision (qwen/qwen3.5-9b) inside the same scaffold: same extraction, relation evidence, action vocabulary, and transition semantics. Two decision baselines isolate the contribution of the scaffold itself: a zero-shot LLM decision baseline (no governance framing; 0.700 accuracy, invalid-commit 0.606) and a six-shot run with 174/180 predictions. The latter is scored coverage-aware by aligning the six missing IDs as INVALID (accuracy 0.7833; macro-F1 0.7692) and remains `incomplete`, not a completed-run comparison (§7.2).

## 4.6 Memory operations and lineage

`src/ask/memory/operations.py` implements `insert_active`, `supersede` (links lineage, marks the prior inactive), `supersede_evict`, `retrieve_active` (excludes superseded records), and `get_lineage`. Lineage is what makes supersession auditable: the losing record remains queryable with its link to the superseding record, rather than being deleted or silently overwritten — the same auditability argument made formally by TOKI's audit rows [@wang2026toki] and operationally by Zep's invalidation timestamps [@rasmussen2025zep], here scored directly via the lineage-integrity metric.

## 4.7 Retrieval and answer-context compilation

Retrieval is dense (MiniLM-L6-v2, max sequence length 256, k=16) with neighbor expansion (±2 turns), assistant/raw-user context pools, and query-gated historical lineage (historical context is offered only when the question requests history). Answer-context compilation reranks for the answer, applies cross-session diversity (v8), and trims to a ~12,000-token budget. The answerer (qwen3.5-9b, temperature 0) uses per-competency prompts with a WORK→FINAL scaffold. These retrieval-side mechanisms matter for Chapter 8: grounding supply is the dominant failure family in the contaminated v7 SSP diagnostic, while the later top-up shows that results cannot be carried across configurations.

## 4.8 Judging and normalization

`LongMemEvalGrader.grade()` applies ordered guards (blank, degenerate, refusal, abstention) before the token guard; `_normalize_text()` collapses spelled-out cardinals and multiplicatives ("twice"→"2"); the hard gold-token reject fires only on a provable numeric conflict, with all lexical/entity/date mismatches deferred to the semantic LLM judge. These fixes respond to documented judge false negatives (F6, §8.3) and are themselves part of the audit trail.

## 4.9 Test strategy

Unit and regression tests cover fail-closed extraction (`test_extractor_recovery.py`), decision semantics, lineage operations, merge-by-session-id de-duplication (`merge_run_shards()`), and the guard logic above. The primary standalone, stdlib-only analysis (`scripts/analysis/audit_mgp6_validity.py`) recomputes shortcut probes, held-out metrics, cluster intervals, finite-sample bounds, calibration, risk–coverage, and cost sensitivity from per-item predictions. The older `mcnemar_mgp6.py` item-level analysis remains reproducible but secondary (Appendix E).

## 4.10 Operational modes

The controller supports simulation (no mutation), shadow, assisted (human approval for selected actions), and autonomous modes; ABSTAIN routes to review rather than committing. Deployment guidance (Chapter 9) restricts autonomous supersession to policy-stable, well-audited cases.


# 5. MGP-6 v2: The Diagnostic Instrument

## 5.1 Purpose and status

MGP-6 v2 is an **author-designed 180-scenario diagnostic slice**, not an independent community benchmark; every claim in this thesis phrases it as such. Its purpose is to isolate write-time governance competence — when to keep, when to supersede, when to abstain — under controlled conflict structure, so that decision failures are attributable and countable. Verified against the raw JSONL on 2026-07-12 (`benchmarks/mgp6/data/mgp6_v2.jsonl`).

## 5.2 Composition

| Property | Value |
|---|---|
| Scenarios | 180 |
| Conflict types | T1–T6, 30 each (type definitions: `benchmarks/mgp6/mgp6_v2_spec.md`; T3 = implicit conflict) |
| Gold actions | SUPERSEDE 90, ABSTAIN 66, KEEP 24 |
| Splits | train 60 / dev 30 / test 90 |
| Query modes | direct_recall 108, premise_resistance 45, implicit_application 27 |

The gold-action distribution is author-imposed rather than population-derived. SUPERSEDE is the majority class (90/180), while ABSTAIN and KEEP account for 66 and 24 items. Macro-F1 therefore accompanies accuracy, but neither metric repairs the more serious shortcut defect: conflict type deterministically identifies the action in this pilot. The distribution must not be interpreted as an estimate of deployment prevalence.

## 5.3 Unit of analysis and split policy

Each scenario has a stable `scenario_id`, an interaction context establishing prior memory, a candidate event, a gold action, a conflict type, a split, and a query mode for the downstream probe. Evaluation joins by stable ID. The rule controller was developed against train/dev; therefore the **test-split figures (n=90) are always reported first** and full-corpus figures second (§7.2), a split-hygiene rule enforced by the claims matrix.

## 5.4 Query modes: probing the state, not just the decision

Each scenario carries a downstream probe in one of three modes: **direct recall** (does the current value surface?), **premise resistance** (the probe asserts a stale or false premise; a governed system must resist it), and **implicit application** (the current value must be used without being named). These modes connect decision correctness to memory-state behavior; premise resistance in particular is where the rule and LLM controllers diverge most sharply (1.0 vs 0.0889, §7.2). The construct is adjacent to STALE's read-side premise-resistance probing [@chao2026stale]; MGP-6 v2 differs in scoring the *write actions* that produce the probed state.

## 5.5 Annotation evidence — stated precisely

Two distinct components, never to be conflated (source of truth §1.2):

1. **One independent annotator** covered the 90-item test split (`benchmarks/mgp6/annotations/human/`): raw agreement **0.9889** [0.9667, 1.0], **Cohen's κ 0.98146** [0.93997, 1.0], macro-F1 0.9913, exactly **one disagreement** — `MGP6V2-T3-TEST-016` (implicit conflict; annotator ABSTAIN vs gold SUPERSEDE). Caveats: n = 1 annotator; the annotator's independence and human identity rest on author attestation; this is **not** multi-human inter-annotator agreement.
2. **A four-LLM audit panel** (geminiPro, gptSolHigh, kimi, z) over the same 90 items: **Fleiss κ 0.9815**, unanimous on 88/90, per-model agreement with gold 1.0 / 0.9778 / 1.0 / 1.0, majority vote **100%** versus gold. This is a model audit, not human IAA.

Additional disclosures: the human review sheet exists but is 0/180 filled; dataset documentation dated 2026-07-10 predates both annotation sets (2026-07-11) and wrongly states agreement was unmeasured — reconciled in this thesis and flagged for the release. The single disagreement is retained as an adjudication item and used for sensitivity discussion (§8.4), not silently relabeled. Because the labeling manual was authored alongside the scenarios, the panel may share the author's reading; this construct-validity limit is threat C2 in Chapter 9.

![Annotation agreement.](../docs/figures/figure_04_annotation_agreement.png)

## 5.6 Baselines embedded in the instrument

Four reference systems establish what the slice measures: B1 no-memory, B2 flat retrieval, B3 recency preference, B4 naive overwrite. B2–B4 cannot express abstention (invalid-commit rate 1.0 by construction on gold-ABSTAIN items), which is precisely the governance gap the instrument is designed to expose; consequently their comparisons with the controller are diagnostic, not general-capability results (§7.4, threat S3).

## 5.7 Relationship to LongMemEval-M

The stratified LME-M slice (180 items, 6 competencies × 30, seed 0, built deterministically by `scripts/build_stratified_slice.py`; the underlying LongMemEval data is external and not redistributed) addresses the downstream layer: whether governed memory supports later answers over long histories [@wu2025longmemeval]. A system can occupy any cell of the decision-correct × answer-correct table. Chapter 7 uses the archived downstream runs only as failure analysis because provider contamination, replay selection, and incomplete coverage prevent a clean estimate of cross-layer association.

## 5.8 Known metric issues (disclosed, excluded from claims)

As shipped, `over_forgetting_rate` and `under_forgetting_rate` saturate at 1.0 for every system and are uninformative; they appear in no claim in this thesis (ledger `known_metric_issues`). The `invalid_commit` metric was revised during the project; all reported numbers use the revised definition, and pre-revision `.bak` files are preserved (threat I6).


# 6. Experimental Methodology

## 5.9 MGP-6 v4.3 final release: remediation, validation, and boundaries

The v4.3 release is a successor diagnostic, not a relabeling of v2 or a basis
for rewriting the historical v2 results above. A v4.1 shortcut review found that
surface lexical and structural features could recover the intended action without
the required reasoning over authority, scope, time, identity, and prior memory.
Mechanical fixes to schemas, identifiers, hashes, and manifests were therefore
kept separate from a substantive v4.2 content redesign. Review then proceeded at
the semantic-component level: KEEP, SUPERSEDE, and ABSTAIN variants were jointly
inspected, label-specific explanations were removed, and balanced factual
evidence plus controlled distractors replaced surface rewriting.

The final v4.3.0-human-validated-final release contains 900 human-authored,
template-guided, controlled synthetic items in 100 semantic components and 20
domains. Components are the locked split unit: train has 180 items from 20
components, development has 180 from 20, and hidden has 540 from 60. Each split
is exactly action-balanced, and each domain contributes one component to train,
one to development, and three to hidden. The release passed duplicate,
near-duplicate, model-field allowlist, shortcut-audit, deterministic-build, and
archive-manifest gates. These facts establish release construction controls; they
do not establish real-world generalization.

Two human annotation packets cover all 900 final items and agree on every action
(raw agreement 1.0; Cohen's kappa 1.0). No item was excluded and no action-label
adjudication was required. Both reviewers marked all 300 ABSTAIN items as
intentionally ambiguous scenarios; that flag records designed ambiguity rather
than uncertainty about the gold action. The dataset-owner attests to human
completion. The builder validates schemas, coverage, content hashes, agreement,
and the attestation, but does not independently authenticate reviewer identity
or annotation duration; this is a provenance limitation, not evidence of an
independent audit.

The release has a strict public/private architecture. Public train and
development records expose only the evidence required to make a decision;
model-facing objects remove gold labels, design targets, component information,
private IDs, and annotator metadata. Hidden inputs, hidden gold, final human
gold, completed annotations, private mappings, source-aligned consensus, and
private audits are stored only in a gitignored local boundary. The single
pre-registered v4.3 hidden prediction was made only after configuration freeze,
coverage validation, and prediction-file hashing. Aggregate final results are
reported in §6.8 and §7.10; no hidden record, gold label, component mapping, or
annotation content is included in this thesis.


## 6.1 Evidence policy: the ledger and claim eligibility

Run provenance comes from `artifacts/results_ledger.json` v1.1; scientific interpretation is superseded by `artifacts/analysis/mgp6_validity_audit.json`. The failed shortcut gate makes MGP-6 v2 policy rows diagnostic regardless of their older ledger label. Mapping-dependent adapters, incomplete runs, and every LongMemEval row remain non-primary. Annotation is described as one independent annotator plus a separate model panel, never human IAA.

## 6.2 Systems under test (MGP-6 v2, n = 180)

| System | Description |
|---|---|
| B1 no-memory | answers without a store |
| B2 flat retrieval | stores everything, retrieves by similarity; no write decisions |
| B3 recency | prefers most recent record; no abstention |
| B4 naive overwrite | new information always replaces old; no abstention |
| Reference policy | deterministic lexical predicate policy used by the released MGP-6 prediction artifact; not the prototype five-feature scorecard |
| LLM controller | full ASK with qwen/qwen3.5-9b as the decision policy |
| Zero-shot LLM decision | same model asked for the action without the governance scaffold |
| Few-shot (6-shot) LLM decision | 174/180 predictions; six missing IDs scored INVALID for a coverage-aware bound (0.7833 / 0.7692); `incomplete` |
| External adapters | Mem0 2.0.11, Letta (MemGPT), Graphiti 0.29.2, MemOS via adapter harnesses |

External-adapter scoring requires an action mapping because these systems emit NOOP rather than ABSTAIN. Those mapped rankings are retained in the artifact audit but excluded from primary comparisons. A successor study must use each system's native observable operations and resulting state.

## 6.3 Ablations

Four single-component removals from the full rule controller, same items and scaffold: **no_abstain** (forced binary commit), **no_provenance**, **no_typing**, **no_lineage**. Their within-generator failure signatures (§7.3) are mechanism diagnostics: they show how this implementation changes when a switch is removed, but do not independently establish that each component is necessary in other datasets or controllers.

## 6.4 LongMemEval-M protocol

Stratified 180-item slice (6 × 30, seed 0). Five systems (B1–B4, controller) were run under the v7 configuration (answerer qwen3.5-9b, judge google/gemma-4-31b-it); the run is **diagnostic only** due to documented provider contamination (§7.6). The v8 failure replay re-executed exactly the 70 v7 controller failures under a changed configuration and is `failure_replay_only`, not an evaluation of the full slice. The complementary Modal top-up targeted 110 prior v7 successes but completed only 84, so it is `incomplete`; it nevertheless provides decisive counter-evidence to carrying all successes forward (§7.7). The frozen final-1.1 protocol specifies a homogeneous full-180 rerun with qwen/qwen3.5-9b and a Gemma judge under a fixed provider and retry policy. Its API smoke failed before inference because the supplied OpenRouter credential returned HTTP 403, so the run is `externally_pending` and no LongMemEval value is final.

## 6.5 Metrics

Decision layer: action accuracy, macro-F1, per-action F1, confusion counts. Commit safety: invalid-commit rate (share of gold-ABSTAIN items on which the system commits a write). Memory state: lineage integrity; stale-retrieval rate. Probe behavior: premise resistance; implicit application. Downstream (LME-M): judge-graded answer accuracy with per-competency decomposition and stratified bootstrap CIs. Formal definitions in Appendix C. Excluded as uninformative: the shipped over-/under-forgetting rates (§5.8). Premise resistance and invalid-commit are bespoke metrics defined in `metrics_mgp6.py` and are interpreted descriptively, not as externally validated constructs (threat C5).

## 6.6 Statistical analysis

The primary analysis uses the held-out 90-item test split and 10,000-replicate paired cluster bootstrap over `template_family_id`, repeated with minimal-pair groups plus singleton items. Both item-weighted and family-macro estimates are reported. Exact item-level McNemar is secondary because within-family independence is doubtful. Zero event counts receive one-sided finite-sample upper bounds. No superiority, equivalence, or non-inferiority language is licensed without a pre-specified contrast and margin. On LongMemEval, no hypothesis test is computed because no clean comparative design exists. Reproduction: `python3 scripts/analysis/audit_mgp6_validity.py`.

## 6.7 Leakage and researcher-degrees-of-freedom controls

Train+development lookup probes over type, conflict type, and public metadata precede policy interpretation. Conflict type reaches 1.000 test accuracy and therefore fails the construct-validity gate: test-first split hygiene alone is insufficient. The v7→v8 fix loop had no confirmation set, so its output is `failure_replay_only`; overrides remain separate from raw results; and invalid, incomplete, mapped, and superseded runs are excluded from primary claims.

## 6.8 MGP-6 v4.3 experimental protocol and completed hidden run

MGP-6 v4.3 uses train for loader and engineering checks, and development for
prompt, model, configuration, ablation, cost, and latency selection. Each system
submits one strict record, `{"public_id":"MGP43-...","action":"KEEP"}`;
the validator rejects missing, duplicate, unknown, extra, and invalid-action
records. Public loading and prompt construction are deterministic, prediction
writing is resume-safe, and raw-response logs record latency, token, retry, and
failure accounting without private fields.

Before hidden prediction, the release and split hashes, provider and exact model
ID, prompt and system-prompt hashes, decoding, seed, retry policy, timeout,
concurrency, evaluator version, code commit, environment lock, and prediction
schema were frozen and recorded. The selected public-indexed-evidence ASK live
controller with qwen/qwen3.5-9b was then run exactly once on the 540-item hidden
split. Its prediction file was complete, duplicate-free, and sealed with
SHA-256 e6a598799115c9fc80ae3e731f1b5d59a4947e48df5356b12ba518bafb846806
before the local-private scorer opened hidden gold. A transport disconnect after
432 durable predictions was recorded; the frozen run resumed only the remaining
108 records and did not change controls or duplicate IDs.

The private evaluator reports accuracy, macro-F1, per-class precision/recall/F1,
confusion matrix, coverage, selective and abstention metrics, and a
5,000-replicate component-cluster bootstrap with seed 4301. It does not expose
gold records in its aggregate output. Provider telemetry supplies latency,
tokens, failures, retries, and invalid-response counts, but no price field; cost
is therefore recorded as unavailable. LongMemEval remains a separate external
evaluation, not a substitute for this controlled diagnostic. Because only one
final v4.3 configuration was pre-registered, there is no final hidden baseline,
ablation, or paired comparison.


# 7. Results

## 7.1 How to read this chapter

The construct-validity gate precedes every controller result. MGP-6 v2 is an author-designed pilot and its ledger label does not override the newly measured shortcut failure. Policy scores below are diagnostic observations on this collection, not estimates of general memory-governance capability. Mapping-dependent external rows and every LongMemEval row are excluded from primary comparisons.

**Shortcut probes fitted on train+development and evaluated on test:**

| Probe (no dialogue or memory state) | Accuracy | Macro-F1 |
|---|---:|---:|
| Type only | 0.9667 | 0.9471 |
| Conflict type only | **1.0000** | **1.0000** |

Conflict type deterministically identifies the action. This is the chapter's primary result: the pilot cannot distinguish evidence reasoning from scenario-family recognition. Cluster bootstrap quantifies dependence inside the collection but cannot repair this construct failure.

## 7.2 MGP-6 v2 policy diagnostics

Test split first (split-hygiene rule), full corpus second.

**Lexical reference policy.** Test split (n=90): action accuracy **0.8889**, macro-F1 **0.9145**. Full corpus (n=180): 0.9222 / 0.9399. The released predictions were generated by deterministic lexical predicates, not the prototype five-feature weighted scorecard. On test, the reference makes 0/33 action false commits, with a one-sided 95% upper bound of 0.0868; it misses 10/45 required updates and unnecessarily abstains on 10/57 non-ABSTAIN items.

**Structured LLM policy (qwen/qwen3.5-9b).** Test split: 0.9000 / 0.9040. Full corpus: 0.8889 / 0.8913. On test it makes 2/33 action false commits and misses 7/45 updates. Its test accuracy is numerically above the reference policy.

**Secondary full-corpus mechanism table (n = 180; includes train and development):**

| System | Accuracy | Macro-F1 | Invalid-commit | Eligibility |
|---|---|---|---|---|
| Lexical reference policy | 0.9222 | 0.9399 | 0.0 | diagnostic |
| Structured LLM policy (qwen3.5-9b) | 0.8889 | 0.8913 | 0.0758 | diagnostic |
| Zero-shot LLM decision | 0.700 | 0.6657 | 0.606 | diagnostic |
| B4 naive overwrite | 0.4222 | 0.2203 | 1.0 | diagnostic |
| B3 recency | 0.4222 | 0.2203 | 1.0 | diagnostic |
| B1 no-memory | 0.3667 | 0.1789 | — | diagnostic |
| B2 flat retrieval | 0.1333 | 0.0784 | 1.0 | diagnostic |
| Few-shot (6-shot) decision | 0.7833 | 0.7692 | — | incomplete: 174/180 predictions; 6 missing scored INVALID |

The few-shot row is a **coverage-aware bound**, not a completed-run comparison. Its 174 predictions were aligned to the 180 gold IDs and the six missing IDs were scored INVALID. It is excluded from the pre-specified significance family and from any claim that assumes complete coverage.

## 7.3 Ablations (n = 180; within-generator diagnostics)

| Configuration | Accuracy | Macro-F1 | Distinct failure signature |
|---|---|---|---|
| Full controller | 0.9222 | 0.9399 | — |
| − abstention | 0.5556 | 0.4278 | invalid-commit 0.0 → **1.0** |
| − provenance | 0.700 | 0.7428 | invalid-commit → **0.606** (identical to the zero-shot baseline's rate) |
| − typing | 0.7889 | 0.5680 | **KEEP F1 → 0.0** |
| − lineage | 0.9222 | 0.9399 | action labels unchanged; **lineage integrity 0.8556 → 0.3689** |

The lineage ablation is a useful within-generator mechanism check: action labels remain identical while the instrument's lineage score falls by more than half. It illustrates why decision and state metrics should be reported separately, but author alignment and the pilot's shortcut failure prevent treating the magnitude as an independent causal estimate.

## 7.4 Held-out clustered comparison and historical item tests

On test, reference minus structured-LLM accuracy is **−0.0111**. The paired template-family cluster interval **[−0.0938, 0.0625]** includes zero (48 test families); exact item-level McNemar has b=4, c=5, p=1.0. The reference family-macro interval is [0.8125, 0.9688] and the structured-LLM interval is [0.8333, 0.9688]. These data support neither superiority nor non-inferiority.

The table below preserves the earlier full-corpus item-level analysis for audit history. It includes train and development items, assumes item independence, and is not the primary inferential result.

| Pair | RD (A−B) | RD 95% CI (Newcombe) | b / c | OR | Holm p | Decision |
|---|---|---|---|---|---|---|
| Rule vs B4 naive overwrite | +0.5000 | [+0.4230, +0.5690] | 90 / 0 | ∞ | 4.85e-27 | reject H0 |
| Rule vs B2 flat retrieval | +0.7889 | [+0.7181, +0.8382] | 142 / 0 | ∞ | 1.44e-42 | reject H0 |
| Rule vs LLM controller | +0.0333 | [−0.0188, +0.0873] | 14 / 8 | 1.75 | **0.286** | **retain H0 (n.s.)** |
| LLM controller vs zero-shot | +0.1889 | [+0.1096, +0.2664] | 46 / 12 | 3.83 | 1.64e-05 | reject H0 |

Interpretation, in the order that matters:

1. **Reference vs structured LLM is a held-out null with the LLM numerically higher.** It is not evidence of equality, matching, or non-inferiority.
2. **Structured vs zero-shot is descriptive.** The historical full-corpus gap is large, but prompt structure and policy scaffolding are evaluated on a shortcut-leaking pilot; it is not a clean general scaffold-effect estimate.
3. **Reference vs B2/B4 is design-aligned.** The reference encodes the labeling manual while the baselines cannot express the required actions. These rows are mechanism checks, not capability proofs.

## 7.5 Archived external-system mapping sensitivity (non-primary)

Under the favourable NOOP→ABSTAIN upper-bound mapping (NOOP→KEEP mapping in parentheses):

| System | Accuracy | Macro-F1 | Notes |
|---|---|---|---|
| Letta (MemGPT lineage) [@packer2023memgpt] | 0.678 (0.489) | 0.488 (0.302) | |
| Mem0 2.0.11 [@chhikara2025mem0] | 0.622 (0.400) | 0.442 (0.249) | invalid-commit 1.0 |
| Graphiti 0.29.2 [@rasmussen2025zep] | 0.383 (0.139) | 0.219 (0.104) | |
| MemOS [@li2025memos] | 0.144 | 0.164 | `diagnostic_only`: supersession inexpressible through its adapter |

These are harness- and mapping-specific transformations, not fair primary capability measurements of the systems' native use cases. They are excluded from the paper's main comparison. A confirmation study must report native write/state/retrieval behavior first and show all action mappings only as sensitivity analyses.

## 7.6 LongMemEval-M: diagnostic results (`diagnostic_only`)

v7 stratified run (n = 180 each; judge google/gemma-4-31b-it):

| System | Correct | Accuracy | SSP |
|---|---|---|---|
| B4 naive overwrite | 114 | **0.6333** | 11/30 |
| ASK controller | 110 | **0.6111** | 11/30 |
| B2 flat vector | 80 | 0.4444 | 6/30 |
| B3 recency | 43 | 0.2389 | 0/30 |
| B1 no-memory | 9 | 0.05 | — |

Two disclosures are mandatory. **First, the baseline ordering: on this diagnostic slice, naive overwrite (63.3%) outperformed the v7 controller (61.1%).** Any claim of controller superiority on LongMemEval is unsupported by current evidence. **Second, the v7 run is provider-contaminated:** 316 HTTP-402 traces, 388 empty extraction fallbacks cached as valid, at least 12 manual relaunches, and an escalation tier that was a no-op (BIG_MODEL == FAST_MODEL). Controller per-competency (v7, post-adjudication 110/180; pre-adjudication 108/180): knowledge-update 21/30, multi-session 15/30, single-session-assistant 26/30, single-session-preference 11/30, single-session-user 22/30, temporal-reasoning 15/30. Earlier partial-range probes (v3: 5/10, 4/10; v4: 17/30; v6: 29/40) are superseded diagnostics; v5 and the thinking-mode v8 replay are invalid; both top-up runs are incomplete (§6.7).

## 7.7 Why the failure-replay construction is excluded

The v8 replay re-executed exactly the 70 v7 controller failures under a changed configuration and judge. It produced 25/70 machine-correct items. A historical merge then retained all 110 v7 successes, replaced only the replayed failures, and added four post-hoc Codex/GPT-5 overrides, yielding an archived 139/180 (0.7722) construction. That number is classified `failure_replay_only`: the selection rule makes judge and configuration identity perfectly confounded with prior correctness, the fixes were designed on the same failures, the retained cases inherited v7 contamination, and the four overrides were not independent human adjudications. It is not a system result, an estimate of final-1.1, or a confidence-bound endpoint.

The complementary Modal top-up makes the carry-forward error observable. It targeted the 110 v7 successes and completed 84: **71 remained correct and 13 regressed**. Combining these 84 observations with the 70 replay observations gives **96/154 raw observed correct**. The 26 unresolved items imply full-180 raw bounds of **96/180 = 53.3%** to **122/180 = 67.8%**. If the four replay overrides are shown separately as an adjudicated sensitivity, the corresponding bounds are **55.6%–70.0%**. Thus this observed v8 attempt cannot reproduce the archived carry-forward construction.

For SSP, the complementary evidence is equally important: the top-up observes **8/29 correct**, with one unresolved item, so the maximum is **9/30**. The v7 diagnostic 11/30 and the replay's 0/19 repairs remain useful for causal investigation, but no SSP count can be carried across configurations. The homogeneous final-1.1 full-180 run remains `externally_pending`: its smoke request failed before inference with OpenRouter HTTP 403.

## 7.8 Annotation agreement (inferential evidence about the labels, not the systems)

One independent annotator: raw agreement 0.9889 [0.9667, 1.0], Cohen's κ 0.98146 [0.93997, 1.0], one disagreement (`MGP6V2-T3-TEST-016`). Four-LLM panel: Fleiss κ 0.9815, majority vote 100% vs gold, 88/90 unanimous. Caveats as in §5.5: n = 1 human + model panel, not multi-human IAA.

## 7.9 Hypothesis outcomes

H1 is not identified by the shortcut-leaking pilot; H2 supports neither superiority nor non-inferiority; H3 and H4 remain within-generator mechanism demonstrations; H5 is unsupported. The independently generated v3 confirmation protocol is the required gate for stronger conclusions.

## 7.10 MGP-6 v4.3 final hidden result (one frozen configuration)

The pre-registered ASK live controller attained **0.8481 accuracy** and
**0.8479 macro-F1** on all 540 hidden items. The component-cluster bootstrap
(5,000 resamples, seed 4301) gives 95% intervals of **[0.8037, 0.8889]** for
accuracy and **[0.8021, 0.8894]** for macro-F1. Every gold action has support
180. Per-action precision / recall / F1 is ABSTAIN 0.8554 / 0.7889 / 0.8208,
KEEP 0.7947 / 0.8389 / 0.8162, and SUPERSEDE 0.8967 / 0.9167 / 0.9066.

The gold-by-prediction confusion rows are ABSTAIN: 142 / 30 / 8; KEEP:
18 / 151 / 11; and SUPERSEDE: 6 / 9 / 165, with columns ordered ABSTAIN, KEEP,
SUPERSEDE. Prediction coverage is 1.0. Of 540 outputs, 166 are ABSTAIN, 190
KEEP, and 184 SUPERSEDE; non-abstention coverage is 0.6926, selective accuracy
is 0.8449, and abstention precision/recall is 0.8554/0.7889. Mean / median / p95
model latency is 1673 / 1278 / 2931 ms. One transport failure was recovered by
resume; there were no invalid responses or in-client retries. The provider did
not emit cost fields, so cost is unavailable rather than estimated.

This is one result on a controlled synthetic diagnostic after public-dev model
selection. It is not a comparison against the development-only baselines or
ablations, not a paired test, and not evidence of real-world memory-governance
performance or deployment safety.


# 8. Error Analysis and Discussion

## 8.1 Single-session preference (SSP): a v7 diagnostic taxonomy

In the contaminated v7 run, SSP is the controller's weakest competency: **11/30 correct (0.3667), CI [0.20, 0.5333]**. The failure-only replay repaired 0/19 of those v7 failures, but it used different prompt contexts and therefore does not isolate an answer-model effect. The complementary top-up observes **8/29 correct** with one unresolved item (maximum **9/30**), proving that the v7 count cannot be carried forward as a cross-version result. The taxonomy below is consequently a causal analysis of the **19 v7 failures**, not a final-1.1 evaluation (`docs/research/SINGLE_SESSION_PREFERENCE_FAILURE_ANALYSIS.md`).

**Primary failure categories (n = 19):**

| Primary category | Count | Share |
|---|---|---|
| retrieval-omission | 6 | 31.6% |
| cross-session-contamination | 4 | 21.1% |
| target-attribute-extraction-miss | 3 | 15.8% |
| distractor-entity-binding | 2 | 10.5% |
| polarity-error | 2 | 10.5% |
| unsupported-answer-specificity | 1 | 5.3% |
| immediate-request-vs-enduring-preference | 1 | 5.3% |

**Combined mechanism mentions (primary + secondary, of 19):** retrieval-omission 11; cross-session-contamination 8; distractor-entity-binding 7; target-attribute-extraction-miss 5; unsupported-answer-specificity 3; immediate-request-vs-enduring-preference 2; polarity-error 2.

**Pipeline-layer localization:** retrieval-ranking 12/19 (63.2%); answer-realization 10/19 (52.6%); context-construction (top-k trim) 5/19 (26.3%); attribution/target-binding 5/19 (26.3%); ingestion, extraction, persistence, controller-policy, and judge-scorer 0/19 each. Notably, **no SSP failure was traced to the write-governance policy itself**: the decisive facts exist in the corpus, and for the answer-side cases they were even present in the prompt.

Two families dominate. **Grounding-supply failures** (retrieval-omission + cross-session-contamination: primary in 10/19, present in 15/19): the single supporting session's decisive preference turn is out-ranked by topically similar distractor sessions and trimmed away, and the model then answers from the wrong session or fabricates. The 0/19 replay repair is consistent with that localization but is not causal proof because the replay changed prompt contexts as well as the answer path. **Answer-side binding/realization failures** (primary in 9/19): the decisive fact was in context, but the answer bound the preference to the wrong target, violated an explicitly stated negative constraint (recommending a dis-preferred podcast genre), or over-specified beyond evidence. One item (`1da05512`) is a borderline judge-severity case rather than a clean pipeline defect, and several judge rationales say "fabricates" where the mechanism is distractor binding — the offending tokens are verbatim in retrieved memory.

**Highest-leverage proposed fix (hypothesized, not run):** make preference grounding an explicit, provenance-constrained representation — a typed record (holder / target / attribute / polarity / scope / source-session) whose retrieval is guaranteed for the question's subject — paired with an answer contract that asserts only retrieved-and-grounded preferences and honors stated negatives. The design targets the ~15/19 grounding-supply mentions, while the ~9/19 answer-side failures show why a retrieval-only repair is unlikely to suffice. Necessity and effect size remain untested. The design and its credit-attribution ablation matrix are specified in `docs/research/SINGLE_SESSION_PREFERENCE_METHOD.md`; PrefEval's finding that preference following collapses within ten turns [@zhao2025prefeval] independently motivates the same construct.

## 8.2 MGP-6 error profiles: three systems, three signatures

**Reference policy — conservative, one-directional on the full pilot.** Its 14 full-corpus action errors are SUPERSEDE→ABSTAIN. On test it has 0/33 action false commits, but the one-sided 95% upper bound is 0.0868 and it misses 10/45 updates. This is a measured trade-off inside the pilot, not a population-safety result.

**Structured LLM policy — different error allocation.** Test action accuracy is 0.9000 versus 0.8889 for the reference, with a paired family interval containing zero. It has more action false commits (2/33) but fewer missed updates (7/45). This supports cost-sensitive reporting, not an absolute policy ordering.

**Zero-shot decision baseline — diagnostic gap.** Its lower score and high full-corpus invalid-commit rate show a failure mode worth studying, but label leakage prevents attributing the difference cleanly to the governance scaffold.

**Ablation signatures.** Abstention removal → invalid-commit 1.0; typing removal → KEEP F1 0.0; lineage removal → audit-score decay invisible to action accuracy (0.8556→0.3689). These are distinct within-generator failure signatures, consistent with the motivation behind MemGuard's typing argument [@ha2026memguard] and TOKI's audit rows [@wang2026toki]. They motivate independent component tests; they do not by themselves establish necessity, causal effect size, or external validity.

## 8.3 LongMemEval run-integrity failure classes (F1–F12)

The failure ledger (`docs/audit/CONTROLLERRUN_FAILURE_LEDGER.md`) distinguishes per-item failures (§8.1) from run/pipeline failures, of which the most consequential are: **F1/F2** — HTTP-402 provider no-responses cached as valid empty extractions (316 "402" traces; 388 empty extractions), fixed in v8 by fail-closed extraction; **F9** — relation-classifier no-responses converted to a cached semantic Keep, same fix; **F3/F4** — total-loss replay failures (thinking-mode token exhaustion → 0 predictions; embedder segfaults), fixed by `enable_thinking:false` and a shared embedding server; **F6** — judge false negatives on number-words and dates ("4" vs "four", "Valentine's Day" vs "February 14th"), fixed by guarded normalization with deferral to the semantic judge; **F8** — the v7 escalation no-op; **F5/F11** — provenance defects (misnamed aborted run; a manifest pointing to a non-existent replay directory); **F10** — in-place verdict overrides preserved with originals; and the top-up evidence showing that prior successes cannot be retained by assumption. The general lesson: infrastructure failures that default to "empty but valid" silently corrupt memory state, while selective replay silently biases reported accuracy; fallbacks must fail closed and repairs must be evaluated on homogeneous coverage.

## 8.4 The retained annotation disagreement as construct evidence

`MGP6V2-T3-TEST-016` (implicit conflict): gold SUPERSEDE, independent annotator ABSTAIN. The disagreement sits on the same SUPERSEDE/ABSTAIN boundary as the reference policy's conservative errors, making it a useful candidate for independent adjudication. With one human label and an author-aligned manual, it is not enough to identify a generally hard construct region. It is retained for blinded adjudication; sensitivity is bounded (one item = 1.1% of the test split) and both labels are defensible under the current manual.

## 8.5 Decision–state–answer divergence

The pilot illustrates why the three layers should be reported separately. Within MGP-6, similar action accuracy can coexist with very different premise-resistance behavior, and the no-lineage ablation leaves action labels unchanged while changing the instrument's state metric. Separately, the contaminated LongMemEval slice happens to rank B4 naive overwrite above the controller on answers (63.3% vs 61.1%). Because the first observations are author-aligned and the second is contaminated, these are diagnostic examples rather than clean cross-layer effect estimates. They nevertheless show how a single aggregate can conceal different failure locations and motivate the layered evaluation design (RQ3).

## 8.6 Asymmetric harm and the price of conservatism

The reference policy's full-pilot action errors are conservative, but missed supersession can itself be harmful. Whether the trade is right is policy-dependent: under the frozen commit-averse matrix the reference has lower test loss (0.111 vs 0.189), while under the update-responsive matrix the structured LLM has lower loss (0.433 vs 0.556). The current weights and any prototype score thresholds have not been validated on independent data, so this is sensitivity analysis rather than optimization evidence.

## 8.7 What the near-neighbor cluster implies

Five verified 2026-adjacent works (STALE, Supersede, TOKI, MemGuard, HaluMem) cover read-side staleness probing, the supersession gap, formal write-time contradiction operators, write-time typing, and operation-level evaluation. This thesis is positioned as an **evaluation decomposition and validity audit**: it makes no claim that the individual mechanisms or their conjunction are unprecedented. The convergence supports the importance of the problem, while the deterministic-policy finding of [@reddy2026freshness] motivates independent confirmation rather than validating this pilot by analogy.


# 9. Validity, Ethics, and Limitations

This chapter follows the v1.1 evidence policy and the repository threat analysis; every threat cites a concrete artifact and carries a mitigation status.

## 9.1 Internal validity

| # | Threat | Instance | Status |
|---|---|---|---|
| I1 | Dataset/controller circularity and label leakage | conflict type alone reaches 1.000 held-out accuracy | **failed construct gate**; not repaired by policy comparisons or cluster bootstrap; independent v3 data required |
| I2 | Failure-derived fixes without a confirmation set (LongMemEval v7→v8) | fixes designed on the exact 70 failures then replayed on them | **mitigated for reporting**: replay classified `failure_replay_only`; **open experimentally**: homogeneous rerun required |
| I3 | Adjudication contamination | v7: 108 original judge-correct + 2 manual corrections; replay merge: 4 Codex/GPT-5 overrides that are not independent human adjudication | **mitigated for reporting**: raw/overridden counts separated; overrides excluded from final claims |
| I4 | Provider contamination and carry-forward bias | v7 has 316 HTTP-402 traces and 388 empty fallbacks; top-up finds 13 regressions among 84 observed prior successes | **mitigated for reporting**: no v7/v8 result claim; **open experimentally**: homogeneous rerun |
| I5 | Split hygiene (MGP-6) | controller developed on train/dev; type/action mapping persists across splits | **not sufficient**: test figures are primary but remain diagnostic |
| I6 | Metric revision mid-project | `invalid_commit` semantics revised; `.bak` preserved | **mitigated**: revised definition used throughout |

## 9.2 External validity

| # | Threat | Status |
|---|---|---|
| E1 | MGP-6 v2 is an author-designed diagnostic slice, not a community benchmark | **open**: mapped external-system comparisons do not provide independent validation; v3 protocol required |
| E2 | LongMemEval evaluated on a 180-item slice, not the full 500 | **open** |
| E3 | Single base model (qwen3.5-9b) and single seed; CIs reflect item sampling, not run variance | **open** |
| E4 | External-adapter numbers are harness- and mapping-specific | **partially mitigated**: both NOOP mappings reported; MemOS flagged bound-only |
| E5 | Synthetic-template dependence (templates, labels, and reference policy authored together) | **confirmed threat**: conflict/type shortcut succeeds despite family-disjoint splits |

## 9.3 Construct validity

| # | Threat | Status |
|---|---|---|
| C1 | "Human IAA" would be a mis-description: evidence is n=1 human + 4-LLM panel | **partially mitigated** by the mandated phrasing; **open**: multi-human IAA; review sheet 0/180 |
| C2 | Panel may share the author's reading (manual unambiguous by construction) | **open** |
| C3 | Shipped forgetting metrics uninformative (saturate at 1.0) | **mitigated by disclosure**: excluded from claims |
| C4 | Judge as construct proxy on LongMemEval (known false-negative classes) | **partially mitigated**: guard fixes, deferral to semantic judge, logged adjudication |
| C5 | Premise resistance and invalid-commit are bespoke metrics | **partially mitigated**: defined in code; interpreted descriptively |

## 9.4 Statistical-conclusion validity

| # | Threat | Status |
|---|---|---|
| S1 | Small and clustered n (90 test items, 48 test families; SSP strata 30) | **partially mitigated**: family/minimal-pair bootstrap and exact counts; external uncertainty remains open |
| S2 | Multiplicity | **mitigated**: Holm over the pre-specified 4-test family |
| S3 | Tautological rule-vs-weak-baseline comparisons (OR = ∞ by design) | **mitigated by framing**: "not sampling noise", not capability proof |
| S4 | The reference-vs-LLM null is easy to misreport as equality or non-inferiority | **mitigated**: test RD −0.0111 and family interval reported; no margin-based claim |
| S5 | Selective replay and judge heterogeneity invalidate the archived 139/180 construction | **mitigated for reporting**: `failure_replay_only`; top-up bounds reported; **open experimentally**: homogeneous rerun |
| S6 | Direction can invert on LongMemEval (B4 63.3% > controller 61.1%) | **open**: no comparative claim until rerun |

## 9.5 Priority actions (decreasing validity impact)

1. Execute the role-separated MGP-6 v3 confirmation protocol: independent writers, all actions within every family, long trajectories, sealed labels, and shortcut rejection gates.
2. Recruit three blinded human annotators for the confirmation test and retain raw labels plus independent adjudication.
3. Evaluate component-oracle and predicted-component pipelines with family-clustered, cost-sensitive analysis.
4. Run external memory systems with native observable metrics; treat action mappings only as sensitivity analyses.
5. Execute a complete homogeneous downstream run only after its input, provider, judge, and provenance gates pass.

## 9.6 Ethics, privacy, and dual use

A system that supersedes and audits memories can be abused to rewrite records or manufacture provenance; a system that retains them enables surveillance, extraction, and membership inference [@carlini2021extracting; @shokri2017membership; @bender2021dangers; @weidinger2022taxonomy]. Mitigations in this project's scope: lineage is append-only and superseded records are preserved rather than destroyed; ABSTAIN routes ambiguity to review instead of committing; the evaluation data is synthetic (MGP-6) or externally licensed and not redistributed (LongMemEval); no personal data of real users is stored. Deployment beyond research requires access control, dual control for bulk operations, and organizational governance consonant with risk-management frameworks [@nist2023airmf]; alignment techniques at the model layer [@ouyang2022training; @bai2022constitutional] complement but do not replace the deterministic write boundary. The governance controller is an engineering framework, not legal advice; "supersede" and "abstain" here are epistemic operations, not compliance guarantees.

## 9.7 Reproducibility statement

Released: code, MGP-6 v2 data, per-item predictions, the 10,000-sample construct-validity audit, cluster intervals, cost sensitivity, bibliographic checks, and the v3 confirmation protocol. The v4.3 final configuration, freeze authorization, aggregate hidden metrics, and prediction hash are reproducibly recorded, while hidden records and gold remain private. The few-shot run is incomplete; mapped external systems and all LongMemEval evidence are non-primary. Independent v3 construction and three-human annotation remain unexecuted. Documentation follows datasheet/model-card practice [@gebru2021datasheets; @mitchell2019modelcards].


# 10. Conclusion and Future Work

## 10.1 Conclusion

This thesis treats the memory write as the governed object: an explicit KEEP/SUPERSEDE/ABSTAIN decision over typed, provenance-tracked, lineage-preserving records, measured separately at action, stored-state/lineage, and answer layers. Its strongest empirical conclusion is methodological and negative. MGP-6 v2 fails a construct-validity gate because conflict type alone reaches 1.000 held-out accuracy. On that pilot, the lexical reference policy obtains 0.8889 test accuracy versus 0.9000 for the structured LLM, with a paired family interval containing zero. The reference has 0/33 observed action false commits but a one-sided upper bound of 0.0868 and 10/45 missed updates; cost matrices reverse the preferred policy. Full-corpus ablations demonstrate measurement behavior, especially that lineage corruption can be invisible to action accuracy, but do not provide independent validation. Incomplete, mapped, contaminated, and selection-biased external/downstream results are excluded from primary claims. The resulting contribution is an auditable evaluation decomposition, released validity analysis, and an independently generated successor protocol—not controller superiority or deployment safety.

## 10.2 Answers to the research questions

**RQ1.** A governed write path can make actions and state transitions explicit and auditable. The current pilot does not establish that its lexical reference policy generalizes or matches an LLM.

**RQ2.** The pilot exposes useful failure signatures and, crucially, exposes its own label shortcut. It is suitable for mechanism debugging, not independent capability estimation.

**RQ3.** Decision metrics (accuracy, macro-F1, per-action confusion), commit safety (invalid-commit), state metrics (lineage integrity, stale retrieval), probe behavior (premise resistance), and judged answers must be reported separately; two shipped forgetting metrics fail and are disclosed as failing (Chapters 6–7).

**RQ4.** Family/minimal-pair clustering, shortcut probes, finite-sample safety bounds, and cost sensitivity materially weaken the original claims. The policy comparison is a null; the downstream track survives only as excluded failure analysis.

**RQ5.** A frozen ledger with claim-eligibility labels, mandatory phrasing rules, co-reported raw/adjudicated numbers, and enumerated invalid runs keep thesis, papers, and code consistent — including where the consistent statement is "not final" (Chapters 6, 9, Appendix F).

## 10.3 Future work

Immediate: execute `benchmarks/mgp6/MGP6_V3_INDEPENDENT_PROTOCOL.md` with writers separated from controller design, three blinded human annotators, all three actions inside every conflict family, long trajectories, hidden labels, and pre-unblinding shortcut gates. A family holdout over v2 alone is insufficient because the label mapping persists across families.

Next (designed, hypothesized): the provenance-constrained typed preference record and answer contract for SSP (`SINGLE_SESSION_PREFERENCE_METHOD.md`), with its credit-attribution ablation between grounding-supply and answer-side repairs.

Longer-term: evaluate oracle versus predicted components, multiple model families and seeds, native external-system operations, and one complete homogeneous downstream pipeline; connect the operational policy to non-prioritized belief revision [@alchourron1985theory] and multi-principal governance [@ren2026gatemem].

The broader conclusion stands independent of the pending cells: a memory-capable agent should be judged not only by what it recalls, but by what it declines to commit, what it supersedes with auditable lineage, and whether its evaluation can tell those apart.


# Appendix A. Data and Record Schemas

## A.1 MGP-6 v2 scenario row (schema: `benchmarks/mgp6/mgp6_schema_v2.py`; spec: `mgp6_v2_spec.md`)

Fields (abridged): `scenario_id` (stable ID, e.g. `MGP6V2-T3-TEST-016`), `type` (T1–T6), `split` (train/dev/test), `context` (prior-memory-establishing turns), `candidate` (new event), `gold_action` (KEEP/SUPERSEDE/ABSTAIN), `query` + `query_mode` (direct_recall / premise_resistance / implicit_application), `gold_answer`.

## A.2 Released prediction row (abridged)

```json
{
  "scenario_id": "MGP6V2-T1-TEST-016",
  "predicted_action": "ABSTAIN",
  "predicted_memory_state": [
    {"id": "mgp6v2-t1-test-016-m1", "status": "active", "supersedes_id": null}
  ],
  "predicted_answer": "The user's current desk lighting preference is warm light.",
  "confidence": 0.4
}
```

This is an abridgement of the restored released artifact, not a synthetic scorecard trace. Gold labels are joined from the dataset during evaluation, and system/run identity is encoded by the artifact path (for example, `artifacts/mgp6_v2/ref_5systems/controller/predictions.jsonl`).

## A.3 Memory record and lineage (store: `src/ask/memory/operations.py`)

Records carry: id, type (e.g. stable_pref / transient_pref / episodic_fact), content, holder, provenance (source turn/session), status (active/superseded), `superseded_by` lineage link, timestamps. `retrieve_active` excludes superseded records; `get_lineage` walks the chain.

# Appendix B. Prompt Contracts (pointer)

All prompt templates are versioned under `prompts/` (`extraction_v0…v_final3.j2`, `relation_stage1_v0.j2`, `relation_stage2_v0.j2`) and referenced by the run configs. Contract requirements: strict JSON output schemas; retrieved memory delimited as untrusted data; the action vocabulary enumerated; unparsable output resolves to no mutation. Judge prompts and guard order are documented in `src/ask/eval/longmemeval.py` (§4.8). Prompts are not duplicated here to keep a single source of truth.

# Appendix C. Metric Definitions

Let \(y_i \in \{K, S, A\}\) be the gold action and \(\hat y_i\) the canonicalized prediction (unknown → INVALID, always incorrect).

- **Action accuracy** \(= \frac{1}{n}\sum_i \mathbb{1}[y_i = \hat y_i]\); **macro-F1** = unweighted mean of per-action F1.
- **Invalid-commit rate** \(= \Pr(\hat y_i \in \{K, S\} \mid y_i = A)\) — commits on gold-ABSTAIN items (definition per revised `metrics_mgp6.py`).
- **Lineage integrity**: share of supersession chains whose links are complete and correct after the run.
- **Stale-retrieval rate**: share of probes on which a superseded record surfaces as current.
- **Premise resistance**: share of premise_resistance probes on which the stale/false premise is rejected.
- **Implicit application**: share of implicit_application probes answered from the current value.
- **LME answer accuracy**: judge-graded correctness; per-competency accuracy with stratified percentile-bootstrap CIs (SSP: n=20,000, seed 0).
- **Primary statistical machinery**: 10,000-replicate paired cluster bootstrap over `template_family_id`, repeated over minimal-pair groups plus singleton items; family-macro and item-weighted estimates; one-sided finite-sample upper bounds for zero event counts; frozen asymmetric expected-cost matrices; descriptive ECE/Brier and risk–coverage diagnostics. Exact item-level McNemar, Holm–Bonferroni, Newcombe intervals, and Wilson marginals are retained only as secondary historical analyses because item independence is doubtful.
- **Excluded**: shipped `over_forgetting_rate` / `under_forgetting_rate` (saturate at 1.0 for every system; ledger `known_metric_issues`).

# Appendix D. Annotation Manual and Adjudication (pointer)

The annotation manual is `benchmarks/mgp6/annotation_manual_v2.md`; the kit builder is `make_annotation_kit.py`; agreement computation is `compute_agreement_v2.py`; raw annotation files live under `benchmarks/mgp6/annotations/human/` (independent annotator) and `mgp6_v2/annotation/` (four-LLM panel). The single open adjudication item is `MGP6V2-T3-TEST-016` (gold SUPERSEDE vs annotator ABSTAIN, implicit conflict). Adjudication protocol: blinded display of the raw item and both labels; evidence spans and policy principle for each; resolution ∈ {released, alternative, both defensible, underspecified}; logged with adjudicators, date, and version impact. Main results use released gold; sensitivity may score the alternative label or exclude the item (±1 item = 1.1% of the test split).

# Appendix E. Reproducibility Commands

```bash
# Environment and offline checks
make test                                   # unit + regression tests
python benchmarks/mgp6/validate_mgp6.py     # dataset integrity

# MGP-6 systems and ablations (see benchmarks/mgp6/EVAL_HARNESS.md)
python benchmarks/mgp6/run_5systems.py
python benchmarks/mgp6/run_ablations.py
python benchmarks/mgp6/run_llm_controller.py
python benchmarks/mgp6/run_llm_decision_baseline.py

# Statistics (stdlib-only, read-only on run artifacts)
python3 scripts/analysis/audit_mgp6_validity.py
# writes artifacts/analysis/mgp6_validity_audit.{json,md}
python3 scripts/analysis/mcnemar_mgp6.py    # prints table + JSON
# item-level historical output: reports/statistical_analysis_raw_output.txt

# Citation coverage and metadata quality
python3 scripts/release/audit_bibliography.py

# SSP analysis
python scripts/evaluation/evaluate_single_session_preferences.py

# Final tables (deterministic transcription of the ledger)
python scripts/analysis/build_final_results.py

# LongMemEval final-1.1 protocol (EXTERNALLY PENDING)
# configs/release/final.yaml + FINAL_EVALUATION_PROTOCOL.md
# The supplied OpenRouter credential returned HTTP 403 before inference.
```

Credentials are supplied only via environment variables; no credential appears in configs, logs, or this repository.

# Appendix F. Artifact Manifest and Claim-Eligibility Vocabulary

| Artifact | Path | Role |
|---|---|---|
| Frozen run ledger | `artifacts/results_ledger.json` v1.1 (sha256 `fea886f1ae746e921e785536e6ce47bea89ec11b99f8f2e75936dc71c6c5185e`) | historical run provenance and archived result transcription; its older policy interpretation is superseded |
| Construct-validity audit | `artifacts/analysis/mgp6_validity_audit.{json,md}` | primary source for MGP-6 shortcut probes, held-out policy metrics, cluster intervals, calibration, finite-sample bounds, and cost sensitivity |
| Final tables | `reports/FINAL_RESULTS.{md,json}` | deterministic ledger transcription |
| Statistics | `reports/STATISTICAL_ANALYSIS.md`, `reports/statistical_analysis_raw_output.txt` | McNemar/Holm/CIs |
| Claims control | `reports/CLAIMS_EVIDENCE_MATRIX.md`; thesis-scoped: `thesis/claims_evidence_matrix.md` | phrasing rules, strength tags |
| Source of truth | `docs/audit/SCIENTIFIC_SOURCE_OF_TRUTH.md` | claim strengths, corrections |
| Error analysis | `reports/ERROR_TAXONOMY.md`; `docs/research/SINGLE_SESSION_PREFERENCE_FAILURE_ANALYSIS.md`; `…/SINGLE_SESSION_PREFERENCE_METHOD.md` | Chapter 8 sources |
| Validity | `reports/THREATS_TO_VALIDITY.md`; `docs/audit/DATA_LEAKAGE_AND_RESEARCHER_DOF.md` | Chapter 9 sources |
| Run reconstruction | `docs/audit/CONTROLLERRUN_RECONSTRUCTION.md`; `…/CONTROLLERRUN_FAILURE_LEDGER.md`; `…/INVALID_AND_SUPERSEDED_RUNS.md` | LongMemEval anatomy |
| Related work audit | `reports/RELATED_WORK_UPDATE.md` | Chapter 2 source |
| Dataset + kit | `benchmarks/mgp6/` (data, manual, metrics, annotation) | Chapter 5 |
| MGP-6 run artifacts | `artifacts/mgp6_v2/…` (per-item predictions + reports) | Chapter 7 |
| LME-M run evidence | external run pointers in `docs/audit/RUN_CLASSIFICATION.csv` | Chapters 7–8; raw external data not redistributed |
| Reproducibility | `reports/REPRODUCIBILITY_CHECKLIST.md`, `Makefile`, `.github/workflows/ci.yml` | Appendix E |

**Claim-eligibility vocabulary:** `diagnostic_only` — informative but not independent validation; `failure_replay_only` — selected by prior failure and excluded from result claims; `incomplete` — missing required coverage; `invalid` — unusable; `externally_pending` — specified but blocked by an external prerequisite. The older `final_candidate` label is a provenance state, not permission to ignore the later shortcut failure.

# References

Citation keys resolve against `thesis/references.bib` (single consolidated bibliography; every cited key was rechecked on 2026-07-15 and is present). Metadata corrections use primary publication records where available; unresolved institutional formatting is kept separate from bibliographic identity. The final bibliography style will be selected after the official University of Tehran template is supplied.
