# Auditable Governance of Long-Term Memory in Language Agents

## The KSA Controller, the MGP-6 Benchmark, Corrected Evaluation, and Reproducible Experimental Practice

**Master's Thesis — Research-Complete Draft**  
**Candidate:** [candidate name to be inserted]  
**Degree programme:** [programme to be inserted]  
**Institution:** [institution to be inserted]  
**Supervisor:** [supervisor to be inserted]  
**Submission date:** [official date to be inserted]

> **Evidence-status notice.** This thesis is complete as a technical and scholarly manuscript over the supplied offline artifacts. It does not fabricate hosted-model results. Experiments that require network access, a current model endpoint, or a missing authoritative runner are explicitly marked *blocked* or *pending*. Historical outputs are described as recovered evidence; recomputed scores are described as re-scores; only commands actually executed in the audit are described as reruns.

---

## Declaration

This manuscript distinguishes original analysis, supplied artifacts, recovered historical outputs, deterministic recomputation, and unexecuted experimental plans. No external-model result is presented as newly executed when the execution environment could not reach the required endpoint. Source archives are retained unchanged and fingerprinted. The canonical repository is an integration layer built beside, rather than over, those sources.

## Abstract

Long-term memory can make language agents more useful, but it also creates a governance problem. A memory-capable agent must decide what deserves retention, what must be updated, what should be ignored, what should be forgotten, and when uncertainty should trigger abstention or human review. These decisions are not equivalent to downstream answer quality. A system can answer a question correctly while retaining prohibited material, or answer incorrectly despite having made a compliant memory decision. Evaluation that collapses policy choice, memory state, and answer behavior into one score therefore obscures both capability and risk.

This thesis presents an auditable KSA Controller and the MGP-6 benchmark as a unified response to that problem. The controller is defined as a policy-governed transition system around an external memory store. It receives an interaction event, extracts relevant evidence, evaluates policy and consent, chooses a normalized action, applies an authorized state transition, and emits an audit record. MGP-6 supplies controlled examples across six memory-governance competencies and supports decision-level evaluation. A recovered 180-item LongMemEval-M slice supports transfer-oriented analysis of downstream memory behavior. An independent 90-item action annotation agrees with the released test labels on 89 items; the remaining T3 case is retained as an adjudication item rather than being silently overwritten.

The thesis also identifies and repairs a consequential evaluation defect. The historical scorer canonicalized predictions but compared them with non-canonical gold strings when computing over-forgetting and under-forgetting. Semantically correct outputs could therefore be reported with maximal error. The canonical evaluator normalizes both sides, exposes raw numerators and denominators, reports conditional and overall rates, and separates decision, memory-state, and downstream-answer metrics. Regression tests lock the repair.

The empirical contribution is deliberately evidence-bounded. The supplied corpus contains 180 MGP-6 records with a 90-item test split, the independent annotation covers all 90 test items, and the recovered LongMemEval-M slice contains 180 items over six competencies. Dataset-integrity tests, deterministic baselines, scorer regression tests, and joinable historical-output re-scoring are executed offline. Hosted Qwen/Gemma validation is packaged as a secret-safe, bounded, resumable protocol but remains unexecuted in this sandbox because external DNS resolution is unavailable. The resulting deliverable is not a collection of disconnected claims: a frozen evidence ledger drives the controller specification, benchmark paper, methods paper, thesis, runbook, and reproducibility checklist.

**Keywords:** long-term memory, language agents, memory governance, forgetting, privacy, auditability, benchmark design, selective prediction, reproducibility, MGP-6, KSA Controller.

## Acknowledgements

The technical package acknowledges the supplied benchmark authors, annotators, maintainers of the historical controller implementations, and the creators of the LongMemEval material from which the recovered evaluation slice was packaged. Institutional and personal acknowledgements should be added before submission.

## Reader's guide

Chapter 1 frames the research problem and questions. Chapter 2 situates the work in language-model memory, retrieval, governance, and benchmark methodology. Chapter 3 formalizes the requirements and threat model. Chapter 4 specifies the KSA Controller. Chapter 5 documents MGP-6 and its annotation. Chapter 6 defines the experimental contract and corrected metrics. Chapter 7 reports the evidence available from the frozen package. Chapter 8 analyzes failure modes and implications. Chapter 9 addresses reproducibility, security, ethics, and governance. Chapter 10 concludes. The appendices provide algorithms, schemas, prompts, run commands, claim controls, and defense material.

## Abbreviations

| Term | Meaning |
|---|---|
| KSA | Knowledge/Keep–Store–Act controller family name used by the supplied project; in this thesis it denotes the audited memory-governance controller as implemented in the canonical repository |
| MGP-6 | Six-competency Memory Governance/Policy benchmark package supplied for this project |
| LME-M | Recovered LongMemEval-M evaluation slice |
| OFR | Over-forgetting rate |
| UFR | Under-forgetting rate |
| PII | Personally identifiable information |
| RAG | Retrieval-augmented generation |
| CI | Confidence interval or continuous integration, depending on context |
| E0–E9 | Registered experiment identifiers in the canonical experiment registry |
| JSONL | JSON Lines format |


# 1. Introduction

## 1.1 Motivation

A language model with no persistent memory is limited: it cannot reliably carry preferences, commitments, unresolved tasks, or user-specific context across sessions. A language model with persistent memory is risky for the opposite reason: it can preserve information beyond the user's intention, allow stale facts to influence future behavior, reproduce sensitive material in unrelated contexts, or make deletion promises that are not reflected in the underlying state. The engineering objective is therefore not “remember as much as possible.” It is to govern memory as a lifecycle under explicit policy.

This observation changes where control must live. Prompting the model to “be careful” is insufficient because memory has side effects. A proposed action must pass through deterministic authorization, the resulting state transition must be verified, and the system must record enough provenance to reconstruct what happened. A useful controller must also preserve uncertainty. When the policy evidence is incomplete or contradictory, forcing a binary keep/forget decision can be more harmful than abstaining.

Existing evaluations often treat memory as an answer-retrieval problem: provide a long interaction history and test whether the model can answer a later question. That view is valuable but incomplete. It does not establish whether the system stored information it was prohibited from storing, deleted the correct object, retained an exception after a blanket deletion request, or updated stale information instead of duplicating it. A governance benchmark must test the decision boundary itself and must expose asymmetric harms.

## 1.2 Research problem

The central research problem is:

> How can a language-agent memory system make, execute, and audit policy-sensitive memory decisions, and how can those decisions be evaluated without conflating governance correctness with retrieval or answer quality?

The problem decomposes into five concerns.

1. **Representation.** The system needs a typed vocabulary of memory actions and a normalized representation of policy evidence, consent, scope, time, and target identity.
2. **Authorization.** A model proposal is not yet an authorized transition. Rules must constrain what the memory store may do.
3. **Execution.** Deletion, update, and retention must affect the intended memory object, not merely produce compliant language.
4. **Measurement.** Evaluation must normalize equivalent labels, preserve raw counts, and report asymmetric errors with correct denominators.
5. **Reproducibility.** Every claim must point to a frozen input, executable command, derived artifact, and status.

## 1.3 Research questions

**RQ1 — Architecture.** What controller decomposition makes long-term memory decisions auditable and prevents a language model from directly mutating memory without policy authorization?

**RQ2 — Benchmark.** Can a compact six-competency benchmark expose memory-governance failures that are hidden by downstream answer accuracy?

**RQ3 — Measurement.** Which metrics distinguish excessive deletion, failure to delete, abstention, memory-state correctness, and downstream answer behavior?

**RQ4 — Reliability.** How sensitive are reported conclusions to label canonicalization, annotation ambiguity, random seeds, and confidence thresholds?

**RQ5 — Reproducibility.** What artifact and claim controls are necessary for a thesis and paper package to remain internally consistent across code, experiments, and prose?

## 1.4 Hypotheses and falsification criteria

The project registers directional hypotheses but does not convert blocked experiment cells into conclusions.

- **H1:** A policy-aware controller will improve macro-F1 on MGP-6 relative to an unconstrained model-only decision path. H1 is falsified if the confidence interval for the paired difference includes no practically meaningful benefit or favors the unconstrained path.
- **H2:** Deterministic authorization will reduce under-forgetting on explicit deletion cases without an unacceptable increase in over-forgetting. H2 is falsified if missed deletion is not reduced, or if non-target deletion rises beyond the predeclared tolerance.
- **H3:** Evidence retrieval and target resolution will contribute distinct gains. H3 is falsified if removing either component does not materially change decision or state metrics.
- **H4:** Decision accuracy and downstream answer accuracy will diverge on at least some test cases. H4 is falsified if all systems and cases produce identical rankings under both layers.
- **H5:** Correct two-sided canonicalization will change at least one historical forgetting metric when legacy labels differ in case, whitespace, separators, or aliases. The regression fixture directly tests this mechanism.

A hypothesis is not considered supported merely because a point estimate moves in the expected direction. The experiment protocol requires raw counts, uncertainty, paired analysis when possible, and disclosure of all registered cells.

## 1.5 Contributions

This thesis makes six contributions.

First, it specifies the KSA Controller as a typed, policy-governed transition system with explicit proposal, authorization, execution, verification, and audit stages. Second, it consolidates the MGP-6 benchmark and its independent action annotation into a frozen evaluation package. Third, it recovers the missing LongMemEval-M fixture from a separate supplied archive, turning a packaging failure into a documented provenance repair. Fourth, it repairs and tests the forgetting scorer. Fifth, it establishes a three-layer evaluation protocol for decision, memory state, and downstream answer behavior. Sixth, it delivers a reproducible research package in which papers and thesis are generated from the same evidence ledger.

## 1.6 Scope

The thesis evaluates the supplied offline artifacts and defines the protocol for model-backed completion. It does not claim that the controller solves all privacy, security, or legal obligations. It does not infer user consent from silence. It does not equate a successful deletion API call with physical erasure across every backup system. It does not present inaccessible hosted-model runs as completed. These boundaries are methodological strengths: they keep the claims testable.

## 1.7 Thesis structure and contribution map

| Research question | Main chapter | Primary artifact |
|---|---|---|
| RQ1 | Chapter 4 | `SYSTEM_SPECIFICATION.md`, canonical source package |
| RQ2 | Chapter 5 | MGP-6 data card and benchmark manuscript |
| RQ3 | Chapter 6 | Corrected evaluator and regression tests |
| RQ4 | Chapters 7–8 | Experiment registry, annotation ledger, robustness protocol |
| RQ5 | Chapter 9 | Provenance manifest, traceability matrix, validation report |


# 2. Background and Related Work

## 2.1 Memory in language-agent systems

The word *memory* covers several mechanisms. Context-window memory places prior tokens directly in the current prompt. Retrieval memory stores chunks externally and retrieves a subset for a new query. Summary memory compresses prior interactions. Structured memory records entities, preferences, commitments, and relationships. Episodic memory stores events with time and provenance. Procedural memory captures reusable strategies or tool routines. Model-parameter memory embeds regularities during training or adaptation. These mechanisms differ in mutability, inspectability, cost, and deletion semantics.

Long context reduces some retrieval overhead but does not remove governance obligations, and long-context models can still use evidence unevenly by position [@liu2024lost]. A system can place disallowed content in a long prompt just as easily as it can retrieve it from a vector store. Retrieval-augmented generation separates storage from generation, yet the retriever and index still need retention, access, and deletion policy [@lewis2020retrieval; @borgeaud2022improving]. Summary memory introduces lossy transformation: a deletion request may target a fact that has already been merged into a summary. Structured stores improve addressability but create schema and identity-resolution risks.

The controller in this thesis is intentionally store-agnostic. It assumes that a memory adapter can enumerate or resolve targets, create, update, suppress, delete, and verify records. This abstraction permits the governance layer to be tested independently from a particular database while still requiring concrete postconditions.

## 2.2 Retrieval is not governance

Retrieval research typically optimizes whether relevant evidence is found and used. Governance asks an earlier question: should that evidence exist and be available to this actor in this context? A high-recall retriever can amplify a retention mistake. Conversely, aggressive deletion can improve privacy but damage continuity and safety if critical commitments or contraindications are erased without scope control.

The distinction motivates a layered causal chain:

\[
\text{event} \rightarrow \text{decision} \rightarrow \text{state transition} \rightarrow
\text{retrieval} \rightarrow \text{answer}.
\]

An error at each link has a different remedy. Decision errors require policy or evidence improvements. State-transition errors require storage adapters, target resolution, or transaction handling. Retrieval errors require indexing or query changes. Answer errors require grounding or generation changes. A single end-to-end accuracy score cannot identify the responsible component.

![Figure 1. Three-layer evaluation within the end-to-end memory pipeline.](figures/figure_06_evaluation_causal_chain.png)

## 2.3 Forgetting as a first-class operation

Forgetting is often modeled as deletion, but operational semantics are richer and distinct from model-parameter unlearning [@cao2015unlearning]. A system may need hard deletion, reversible suppression, expiry, redaction of a field, replacement of a stale value, or removal of an embedding while retaining a minimal audit tombstone. The correct operation depends on policy and system boundaries.

The controller therefore separates the abstract action `FORGET` from the adapter-specific mechanism. The policy may authorize `FORGET` while a deployment maps it to deletion, cryptographic erasure, suppression, or queued deletion. The audit record must state which mechanism was attempted and what verification established. This prevents language-level assurances from masquerading as state-level guarantees.

## 2.4 Consent, purpose, scope, and temporal validity

Memory decisions are contextual. A user can authorize retention for one purpose but not another, revoke earlier consent, request deletion of one record while preserving an exception, or correct a value that invalidates earlier memories. A governance representation therefore needs at least:

- subject and actor identity;
- target object or query;
- action and purpose;
- consent evidence and source;
- scope and exceptions;
- time of event and policy version;
- sensitivity and retention class;
- uncertainty and conflict indicators.

These fields need not all be predicted by a model. Some should come from authenticated session context, policy configuration, or trusted metadata. The controller fuses them but tracks their provenance.

## 2.5 Selective prediction and abstention

Abstention is a safety mechanism when the cost of a wrong action exceeds the cost of delay, connecting this work to selective classification [@geifman2017selective]. Selective classification evaluates performance on covered cases and the fraction of cases covered. For memory governance, the abstention policy should be asymmetric: uncertainty about a low-risk preference may permit a conservative default, while ambiguity about a deletion target may require clarification or review.

Coverage alone is insufficient. A system can attain high selective accuracy by abstaining on nearly everything. The evaluation therefore reports coverage, selective accuracy, risk at coverage, and failure costs. Thresholds are chosen on a development split and frozen before test evaluation.

## 2.6 Benchmark design and annotation quality

A benchmark is a measurement instrument, not merely a file of prompts; its documentation should follow the spirit of datasheets and model reporting [@gebru2021datasheets; @mitchell2019modelcards]. It must state the construct, sampling process, competency coverage, split policy, annotation instructions, ambiguity handling, leakage risks, and limitations. Exact agreement does not guarantee validity; disagreement does not automatically indicate an annotator error. The single retained MGP-6 T3 discrepancy is treated as information about construct boundaries. Sensitivity analysis can score the item under both defensible labels or exclude it with disclosure.

Class imbalance is another concern. Accuracy can look strong when a dominant action class is guessed repeatedly. Macro-F1, per-class recall, confusion matrices, and asymmetric forgetting rates are therefore necessary. Deterministic and stochastic baselines establish whether the benchmark is trivial under class frequencies.

## 2.7 Reproducibility and artifact integrity

Research software frequently mixes raw data, mutable scripts, generated outputs, and narrative documents, creating a form of technical debt that can invalidate evaluation [@sculley2015hidden; @liang2023holistic]. That structure makes it easy to change a scorer without knowing which tables are stale. The present package adopts four separations:

1. **Immutable source evidence:** untouched archives and checksums.
2. **Canonical implementation:** repaired code and tests.
3. **Derived evidence:** profiles, joins, metrics, and ledgers.
4. **Narrative outputs:** papers, thesis, cards, and runbooks.

Every derived artifact is rebuildable. Historical files remain available but are not silently treated as canonical. The status vocabulary—executed, recomputed, recovered, blocked, pending, not applicable—appears throughout the package.

## 2.8 Positioning of the thesis

The work sits between memory-augmented language agents, privacy-aware information lifecycle management, selective prediction, and benchmark engineering. Its novelty is not a claim that any one policy rule is universally correct. It is the integration of explicit memory actions, deterministic authorization, state verification, corrected asymmetric metrics, controlled benchmark competencies, and evidence-traceable reporting.


# 3. Requirements, Formal Problem, and Threat Model

## 3.1 System boundary

Let an interaction event be

\[
e_t = (x_t, u_t, a_t, c_t, \tau_t),
\]

where \(x_t\) is content, \(u_t\) is the authenticated subject, \(a_t\) is the acting principal, \(c_t\) is contextual metadata, and \(\tau_t\) is time. Let memory state \(M_t\) be a set of typed records. Let policy state \(P_t\) include active rules, consent, retention schedules, and access constraints. The controller computes:

\[
(d_t, q_t, r_t) = C(e_t, M_t, P_t),
\]

where \(d_t\) is a normalized action, \(q_t\) is a target or query, and \(r_t\) is a structured rationale with provenance and confidence. An authorization function produces:

\[
auth_t = A(d_t, q_t, e_t, P_t) \in \{allow, deny, review\}.
\]

Only `allow` may trigger a transition:

\[
M_{t+1} = T(M_t, d_t, q_t, e_t).
\]

A verifier evaluates postconditions \(V(M_t,M_{t+1},d_t,q_t)\), and an append-only audit event records proposal, authorization, transition outcome, verification, policy version, and hashes of relevant inputs.

## 3.2 Action vocabulary

The canonical evaluator recognizes a small action vocabulary and aliases. The core actions are:

- `KEEP`: preserve an existing record or authorize retention of a new one;
- `FORGET`: remove, suppress, expire, or otherwise make a target unavailable under the configured semantics;
- `UPDATE`: replace or amend a stale record while preserving provenance;
- `IGNORE`: do not create a memory from the current event;
- `ABSTAIN`: decline autonomous action and route to clarification or review.

Deployment-specific subtypes may refine these actions, but evaluation must map them deterministically to the canonical vocabulary. Unknown labels are preserved as unknown rather than coerced to a plausible class.

## 3.3 Functional requirements

**FR-1 Event normalization.** The controller shall normalize encoding, whitespace, time, identity references, and source metadata without changing substantive meaning.

**FR-2 Evidence extraction.** The controller shall identify consent, revocation, correction, deletion, retention, scope, exception, and sensitivity evidence.

**FR-3 Target resolution.** Destructive or mutating actions shall resolve to explicit memory identifiers or a bounded query whose candidate set is auditable.

**FR-4 Policy evaluation.** The controller shall combine model-proposed evidence with deterministic policy rules and authenticated metadata.

**FR-5 Authorized transition.** The language model shall not directly mutate the memory store. The adapter receives only authorized operations.

**FR-6 Verification.** The controller shall evaluate action-specific postconditions and record partial failures.

**FR-7 Idempotence.** Retried requests shall not create duplicate transitions or delete additional objects beyond the authorized target set.

**FR-8 Auditability.** Each decision shall have an identifier, timestamp, policy version, evidence references, normalized action, authorization outcome, adapter response, and verification result.

**FR-9 Abstention.** The controller shall support review or clarification when policy evidence, target identity, or confidence is insufficient.

**FR-10 Evaluation export.** The system shall export decision, memory-state, and answer-layer artifacts using stable IDs.

## 3.4 Non-functional requirements

The system must be reproducible, secret-safe, fail-closed for destructive ambiguity, observable, testable without network access, and compatible with versioned data. It should minimize retained content in logs, support deterministic seeds, bound retries and model costs, and preserve raw model responses separately from parsed decisions.

## 3.5 Invariants

The controller enforces the following invariants:

1. no mutation without authorization;
2. no destructive mutation without a resolved target or explicit broad-scope authorization;
3. no silent reinterpretation of unknown action labels;
4. no success status before transition verification;
5. no overwrite without preserving prior version or an auditable tombstone, subject to policy;
6. no claim of physical erasure beyond the verified system boundary;
7. no use of a test split for threshold selection;
8. no mixing of recovered historical scores with newly executed inference.

## 3.6 Threat actors and failure sources

The threat model includes accidental and adversarial causes.

- A user may issue ambiguous, contradictory, or malicious instructions.
- A model may hallucinate consent, scope, or target identity.
- Prompt injection in stored content may attempt to influence policy evaluation.
- A retriever may surface material outside the authorized purpose.
- An adapter may report success without applying the intended state change.
- Concurrent updates may produce lost writes or stale verification.
- An evaluator may normalize predictions and gold labels differently.
- A researcher may select favorable metrics, omit failed runs, or copy stale tables.
- Logs may leak the content that the controller was supposed to forget.

## 3.7 Security and privacy controls

Stored content is untrusted data, not executable policy. Policy rules and system instructions are isolated from retrieved memory. The controller applies least privilege to memory adapters, uses idempotency keys, limits destructive query breadth, and redacts audit payloads. Credentials are injected through process environment variables and are never written to source files or result logs. A production deployment should additionally use encrypted storage, role-based access, key rotation, deletion workflows across backups, and independent security review.

## 3.8 Failure taxonomy

Failures are classified along the causal chain:

| Layer | Example failure | Primary diagnostic |
|---|---|---|
| Evidence | revocation phrase not detected | extraction recall by evidence type |
| Decision | `KEEP` chosen instead of `FORGET` | confusion matrix; UFR |
| Authorization | destructive proposal allowed despite ambiguity | policy-rule tests |
| Target resolution | wrong memory object selected | target precision/recall |
| Transition | adapter fails or partially deletes | postcondition verification |
| Retrieval | deleted record still retrieved | state/retrieval consistency |
| Answer | correct memory exists but answer is wrong | answer exact/F1 or judge metric |
| Audit | decision cannot be reconstructed | audit completeness test |
| Evaluation | label aliases mismatched | canonicalization regression |

## 3.9 Acceptance criteria

The offline acceptance gate requires clean canonical unit tests, parseable frozen datasets, unique stable identifiers or documented exceptions, deterministic baseline reproducibility, two-sided label normalization, raw counts for forgetting metrics, and a complete evidence ledger. The hosted-model acceptance gate additionally requires model/version capture, bounded cost, resumability, output parsing tests, independent judge configuration, and complete result manifests.


# 4. KSA Controller Design and Implementation

## 4.1 Architectural overview

The KSA Controller surrounds the memory store with a governance boundary. Its major modules are event normalization, evidence extraction, memory lookup, policy evaluation, action proposal, deterministic authorization, transition execution, verification, and audit emission. The proposal may be model-assisted; authorization and mutation semantics are code- and policy-controlled.

![Figure 2. KSA Controller architecture.](figures/figure_07_ksa_controller_architecture.png)

```text
Interaction event
      |
      v
[Normalizer] --> [Evidence extractor] --> [Target resolver]
      |                    |                       |
      +--------------------+-----------------------+
                           v
                     [Policy context]
                           |
                           v
                  [Action proposal/model]
                           |
                           v
                 [Deterministic authorizer]
                    /       |        \
                  deny    review     allow
                                     |
                                     v
                              [Memory adapter]
                                     |
                                     v
                                [Verifier]
                                     |
                                     v
                                 [Audit log]
```

## 4.2 Event normalization

Normalization handles Unicode compatibility, line endings, whitespace, timezone representation, and structured metadata. It must not erase evidence-bearing distinctions. For example, quotation marks can distinguish a user instruction from a quoted statement, and temporal expressions can determine whether consent predates a revocation. The implementation therefore retains raw content and records normalized derivatives.

Identity normalization is especially sensitive. Display names are not sufficient for destructive operations. The controller uses authenticated subject identifiers where available and marks unresolved co-reference. A request such as “forget what I said about my brother” contains a subject, relation, topic, and potentially broad time scope; it cannot be safely reduced to a keyword match.

## 4.3 Evidence extraction

The evidence extractor produces typed claims rather than an unconstrained paragraph. A representative schema is:

```json
{
  "consent": {"status": "granted|revoked|unknown", "scope": [], "source_spans": []},
  "requested_action": "KEEP|FORGET|UPDATE|IGNORE|ABSTAIN|UNKNOWN",
  "targets": [{"type": "memory_id|topic|entity|time_range", "value": "..."}],
  "exceptions": [],
  "purpose": [],
  "sensitivity": "low|moderate|high|unknown",
  "temporal": {"effective_at": "...", "expires_at": "..."},
  "conflicts": [],
  "confidence": 0.0
}
```

Source spans and provenance allow an auditor to determine whether the proposal rests on actual user language or hallucinated evidence. The extractor may use rules, a model, or both. Deterministic patterns are appropriate for explicit commands and structured settings; a model helps with paraphrase and discourse context. Conflicts are preserved for policy evaluation rather than averaged away.

## 4.4 Memory lookup and target resolution

Target resolution translates a natural-language request into a bounded candidate set. It may combine exact identifiers, entity links, time filters, semantic search, and user/session ownership. Destructive breadth is measured before execution. If a broad request matches many records, policy can require confirmation or staged deletion.

The resolver returns candidates with scores and explanations. Authorization can require that the top candidate exceed a threshold and that the margin over alternatives is sufficient. For blanket deletion requests, the resolver records the query definition and snapshot of matched identifiers so retries remain idempotent.

## 4.5 Proposal generation

The proposal stage consumes normalized event data, evidence, candidate memories, and policy summaries. It outputs a strict schema with action, target, rationale codes, confidence, and requested review state. Free-form rationales may be retained for analysis but are not used as executable instructions.

Prompting follows four principles: policy hierarchy is explicit; retrieved memory is delimited as untrusted data; allowed actions are enumerated; and the model must abstain rather than invent missing consent or target details. The raw response is stored separately from the parsed result. Parse failure yields `ABSTAIN`, not a default mutation.

## 4.6 Deterministic authorization

Authorization is the main safety boundary. A simplified rule order is:

1. validate schema and actor permissions;
2. reject unknown action or unresolved destructive target;
3. apply explicit legal or organizational prohibitions;
4. apply explicit, current user revocation or deletion requests;
5. respect scoped exceptions and latest valid corrections;
6. enforce sensitivity and retention rules;
7. evaluate confidence and conflict thresholds;
8. return allow, deny, or review with reason codes.

Rule precedence is versioned. The model can surface evidence but cannot override a higher-priority rule. A policy simulator runs proposed decisions without mutation, enabling offline benchmark evaluation and predeployment checks.

## 4.7 State-transition semantics

`KEEP` creates or preserves a record only if policy permits retention. Duplicate detection avoids repeated storage of the same fact. `UPDATE` creates a new version linked to the prior state or performs an atomic compare-and-swap, preventing stale overwrite. `FORGET` invokes the configured deletion or suppression mechanism and records target counts. `IGNORE` produces no content-bearing memory. `ABSTAIN` creates a review task or clarification request but no memory mutation.

For each action, the adapter returns an operation ID, affected identifiers, status, and error details. The controller treats partial success as partial, not successful. Retried operations use idempotency keys derived from decision ID and policy version.

## 4.8 Verification

Verification asks whether the intended postcondition holds:

- after `KEEP`, the record is present once, with correct ownership and metadata;
- after `UPDATE`, the current value reflects the authorized correction and the stale value is not returned as current;
- after `FORGET`, targets are unavailable through ordinary retrieval and the adapter reports the expected affected set;
- after `IGNORE`, no new record is attributable to the event;
- after `ABSTAIN`, no mutation occurred and a review or clarification path exists.

Verification should query through both direct storage and the retrieval path when possible, because an index can lag behind the source store. Physical erasure from backups is a separate control that may require asynchronous infrastructure and cannot be inferred from an online read check.

## 4.9 Audit event

A minimal audit event contains:

```json
{
  "decision_id": "uuid",
  "event_hash": "sha256",
  "subject_id": "pseudonymous-id",
  "policy_version": "semver-or-hash",
  "proposal": {"action": "FORGET", "target_ids": ["m-17"], "confidence": 0.94},
  "authorization": {"outcome": "allow", "reason_codes": ["EXPLICIT_DELETE"]},
  "transition": {"operation_id": "op-...", "status": "success", "affected": 1},
  "verification": {"passed": true, "checks": ["not_retrievable"]},
  "created_at": "RFC3339 timestamp"
}
```

The event should minimize sensitive content. Hashes and typed reason codes are preferable to copying full user messages. Audit access itself is privileged and monitored.

## 4.10 Canonical repository

The canonical repository is an integration layer with the following structure:

```text
02_canonical_repository/
  data/
    mgp6_v2/
    annotations/
    longmemeval_m/
  src/ksa_mgp6/
    labels.py
    io.py
    evaluate.py
    cli.py
  tests/
  configs/
  experiments/
  historical_runs/
  legacy_sources/
  scripts/
  provenance/
```

Legacy implementations remain unchanged under `legacy_sources`; historical outputs remain under `historical_runs`. The canonical package supplies a stable evaluator and CLI, not a retrospective rewrite of history.

## 4.11 Label canonicalization

The normalization function applies Unicode NFKC, trimming, case normalization, separator normalization, and explicit alias mapping. Crucially, it is applied independently to gold and predicted labels before every comparison. Unknown values survive as unknown tokens. This design prevents both asymmetric scoring and silent coercion.

Pseudocode:

```text
function canonicalize(label):
    if label is null: return UNKNOWN
    s = NFKC(label)
    s = trim_and_collapse_whitespace(s)
    s = uppercase(replace_separators(s))
    if s in alias_map: return alias_map[s]
    return s
```

## 4.12 Operational modes

The controller supports simulation, shadow, assisted, and autonomous modes. Simulation never mutates state. Shadow mode observes production events and compares proposals with the active system. Assisted mode requires human approval for selected actions. Autonomous mode is reserved for policy-stable, well-calibrated cases and still records audit events. Migration between modes is competency- and action-specific rather than global.

## 4.13 Complexity and performance

Controller latency includes extraction, retrieval, proposal, policy evaluation, adapter execution, and verification. Deterministic policy checks are typically small relative to model and storage latency. Target resolution can dominate for broad deletions. Batching is acceptable for non-urgent maintenance but dangerous when it blurs per-event authorization. Performance evaluation should report p50, p95, and p99 latency, model tokens, retrieval count, adapter calls, and retry rate, all stratified by action.

## 4.14 Test strategy

Unit tests cover canonicalization, rule precedence, target breadth, idempotency, and metric denominators. Contract tests exercise memory adapters. Property tests assert invariants such as “a denied action never mutates state.” Integration tests run decision-to-verification paths against an ephemeral store. Regression tests include the exact scorer bug and the recovered missing fixture. End-to-end hosted-model tests are bounded and resumable.


# 5. MGP-6 Benchmark and Annotation

## 5.1 Benchmark purpose

MGP-6 is treated as a controlled instrument for memory-governance decisions. It does not replace broad conversational-memory benchmarks. Its purpose is to isolate competencies that determine whether a memory-capable agent should keep, forget, update, ignore, or defer a memory operation under policy-relevant context.

The supplied version contains **180 records**, including a **90-item test split**, and spans **6 competencies**. The independent action-annotation package covers all **90 test items**. Exact action agreement is **89/90**; the remaining **1** item, identified as a T3 ambiguity in the audit, is retained for adjudication and sensitivity analysis.

## 5.2 Construct definition

The benchmark construct is *memory-governance decision competence*: the ability to select an authorized memory action from an interaction and its policy context. It is narrower than general helpfulness and broader than keyword detection. A valid item must contain enough evidence for a defensible action or intentionally require abstention.

The six-competency structure is preserved from the supplied data.

![Figure 3. MGP-6 competency distribution.](figures/figure_01_mgp6_competency_distribution.png)

![Figure 4. MGP-6 gold action distribution.](figures/figure_02_mgp6_action_distribution.png) The canonical profile records the exact names and distributions rather than inventing replacements. At an abstract level, the competencies cover explicit retention/forgetting, conflict and correction, scope and exception handling, temporal or lifecycle reasoning, sensitivity/policy constraints, and ambiguous cases requiring conservative action. Any public benchmark description should use the released competency names verbatim from the profile artifact.

## 5.3 Unit of analysis

Each item has a stable identifier, prompt or interaction context, competency label, split, and gold action. Some packages include additional rationale, metadata, or scenario fields. Evaluation is keyed by stable ID. Row order is never used as the only join mechanism because independent annotations and model outputs may be sorted differently.

## 5.4 Split policy

The frozen package exposes training/development/test metadata where present and a 90-item test set confirmed by the audit. Threshold selection, prompt refinement, alias changes, and policy tuning must not use test labels. When the supplied split lacks a dedicated development set for a particular experiment, a deterministic split of the non-test records must be registered before inspecting results.

## 5.5 Annotation process

The independent annotation serves as a reliability check, not an automatic replacement for released gold; nominal agreement statistics should supplement, not replace, item-level adjudication [@cohen1960coefficient]. Annotators apply the canonical action vocabulary using scenario evidence and policy scope. Agreement is computed after stable-ID alignment and two-sided label canonicalization. The audit reports both exact agreement and the disagreement record.

For disagreement, adjudication follows four steps:

1. display raw item and both labels without revealing model outputs;
2. identify the evidence span and policy principle supporting each label;
3. decide whether one label is clearly incorrect, both are defensible, or the item is underspecified;
4. record the resolution, rationale, adjudicators, date, and version impact.

The unresolved T3 item is not silently modified.

![Figure 5. Independent action annotation agreement.](figures/figure_04_annotation_agreement.png) Main results can use released gold, while sensitivity results score the alternative label and optionally exclude the item.

## 5.6 Quality controls

Quality checks include parseability, unique IDs, allowed-label validation, split disjointness, duplicate and near-duplicate analysis, competency/action balance, annotation coverage, and leakage review. The deterministic dataset profile is generated from frozen files and retained as JSON and Markdown. Every correction would require a version increment and changelog entry.

## 5.7 Baselines

Four offline baselines establish measurement sanity:

- majority action on the training/reference distribution;
- stratified random action sampling from observed class frequencies;
- uniform random action sampling over canonical classes;
- oracle sanity check that copies gold and must score perfectly.

Random baselines use registered seeds and should be repeated across multiple seeds for uncertainty. The oracle is not a competitive model; it detects evaluator defects.

## 5.8 Relationship to LongMemEval-M

The recovered LongMemEval-M slice contains **180 items** across **6 competencies** with full histories in the supplied baseline archive. It addresses a different layer: whether memory information supports later behavior over interaction history. The thesis uses it for transfer-oriented and downstream evaluation, while MGP-6 remains the decision-governance instrument.

A system can therefore occupy four quadrants: correct decision and correct answer; correct decision but wrong answer; wrong decision but accidentally correct answer; or wrong decision and wrong answer. Reporting the quadrants prevents answer accuracy from hiding policy violations.

## 5.9 Data statement

The data card documents intended use, out-of-scope use, fields, distributions, annotations, risks, and maintenance. The benchmark should not be used as proof of legal compliance or universal cultural consensus. It is an engineering evaluation of the supplied policy construct.

## 5.10 Frozen profile

The complete machine-readable profile is retained at `03_evidence/DATASET_PROFILE.json`. A bounded snapshot follows:

```json
{}
```


# 6. Experimental Methodology

## 6.1 Experiment philosophy

The experiment plan is registered as E0–E9. Each experiment has a question, inputs, command, metrics, status, and completion criterion. A cell is not complete merely because a historical output file exists. The package distinguishes:

- **executed:** command run in the current audit environment;
- **recomputed:** metrics calculated from frozen predictions and gold;
- **recovered:** artifact found and provenance-linked but not regenerated;
- **blocked:** execution attempted but prevented by an external constraint;
- **pending:** required input or authoritative runner not yet available;
- **not applicable:** cell excluded by design with rationale.

## 6.2 Registered experiments

| ID | Purpose | Primary outputs | Current evidence class |
|---|---|---|---|
| E0 | Dataset and package integrity | profile, checksums, duplicate and schema checks | executed offline |
| E1 | Deterministic and random baselines | accuracy, macro-F1, per-class metrics | executed/recomputed offline |
| E2 | Legacy-output re-score | corrected metrics from joinable outputs | recomputed where joinable |
| E3 | Scorer regression | tests for canonicalization and denominators | executed offline |
| E4 | Controller ablations | component-wise paired results | pending authoritative runner mapping where absent |
| E5 | LongMemEval-M transfer | downstream and state metrics | fixture recovered; runner-dependent cells pending |
| E6 | Hosted-model validation | Qwen primary, Gemma judge protocol | blocked by external DNS in sandbox |
| E7 | Calibration/selective prediction | risk–coverage and threshold analysis | pending confidence-bearing outputs |
| E8 | Robustness | paraphrase, noise, policy-conflict perturbations | pending registered generation/execution |
| E9 | Annotation sensitivity | released vs alternative T3 label | adjudication open; protocol complete |

## 6.3 Systems and ablations

The full system includes evidence extraction, memory retrieval, policy context, proposal generation, deterministic authorization, target resolution, transition verification, and abstention. The minimum ablation matrix removes or substitutes one component at a time:

1. model-only action classification;
2. no policy retrieval;
3. no memory retrieval;
4. no deterministic authorizer;
5. no target-resolution safeguards;
6. no verification;
7. no abstention;
8. rules-only controller;
9. full controller.

Ablations must use the same examples, model version, decoding settings, and seed policy. Destructive-action ablations run in simulation unless the store is ephemeral.

## 6.4 Model-backed protocol

The supplied plan uses Qwen as the primary model and Gemma as an independent judge, with exact model identifiers supplied at runtime rather than frozen without verification. The runner reads credentials only from `OPENROUTER_API_KEY`; it must not print or persist the credential. Model names can be supplied through `KSA_PRIMARY_MODEL` and `KSA_JUDGE_MODEL`.

The protocol is bounded and resumable. Each item has a deterministic request ID. Completed responses are skipped unless `--force` is used. Raw responses, parsed decisions, usage metadata, endpoint model string, timestamps, and errors are written separately. Retries are capped and use backoff. A small smoke test precedes the full run.

The current sandbox could not resolve external hosts, so model-backed execution stopped before authentication. This is recorded as a network-environment block, not a model failure.

## 6.5 Decision metrics

Let \(y_i\) be the canonical gold action and \(\hat y_i\) the canonical prediction.

**Accuracy** is

\[
Acc = \frac{1}{n}\sum_{i=1}^{n} \mathbb{1}[y_i=\hat y_i].
\]

For each class \(c\), precision, recall, and F1 are computed from one-vs-rest counts. Macro-F1 averages class F1 values, giving minority actions equal class weight. The confusion matrix is reported with raw counts.

## 6.6 Corrected forgetting metrics

Define the forget set \(F\), normally the canonical action `FORGET`. Then:

\[
OFR = \frac{\sum_i \mathbb{1}[y_i \notin F \land \hat y_i \in F]}
{\sum_i \mathbb{1}[y_i \notin F]},
\]

\[
UFR = \frac{\sum_i \mathbb{1}[y_i \in F \land \hat y_i \notin F]}
{\sum_i \mathbb{1}[y_i \in F]}.
\]

OFR measures excessive forgetting among cases that should not be forgotten. UFR measures missed forgetting among cases that should be forgotten. The evaluator also reports both numerators, denominators, and overall rates with \(n\) as denominator. Undefined conditional rates are returned as null with a zero denominator, not silently set to zero.

The repaired evaluator canonicalizes **both** \(y_i\) and \(\hat y_i\). The legacy defect canonicalized predictions but not gold values in these calculations. A gold string such as `"forget "` could therefore fail equality with a canonical prediction `FORGET` even though the decision was semantically correct.

## 6.7 Abstention and calibration

For non-abstained set \(S_\theta\) under confidence threshold \(\theta\):

\[
Coverage(\theta)=\frac{|S_\theta|}{n}, \qquad
SelectiveAccuracy(\theta)=\frac{1}{|S_\theta|}\sum_{i\in S_\theta}\mathbb{1}[y_i=\hat y_i].
\]

Risk is one minus selective accuracy or a cost-weighted error. Expected calibration error and Brier score may be reported when class probabilities are available. Thresholds are selected on development data under a declared cost or minimum-coverage constraint.

## 6.8 Memory-state metrics

Decision correctness does not prove execution. State metrics include target precision/recall, transition success, duplicate rate, stale-record rate after update, residual retrieval after forgetting, and idempotence under retry. A state oracle snapshots expected record identifiers before and after each simulated operation.

## 6.9 Downstream answer metrics

LongMemEval-M evaluation can report exact match, token F1, semantic or judge-based correctness, citation/grounding, and abstention. The judge prompt is fixed and blinded to system identity. A human audit sample checks judge reliability. Answer metrics are cross-tabulated with decision and state correctness.

## 6.10 Statistical analysis

Paired bootstrap confidence intervals are preferred for differences because systems evaluate the same items [@efron1993bootstrap]. McNemar's test can assess paired binary correctness. Multi-seed stochastic results report mean, standard deviation, and individual seeds. Multiple comparisons are controlled or clearly labeled exploratory. Effect sizes accompany p-values.

Competency and action subgroups are reported only when sample sizes support interpretation. Small denominators are shown explicitly. No subgroup percentage is presented without its count.

## 6.11 Robustness protocol

Robustness tests preserve the underlying gold policy while varying surface form or irrelevant context. Perturbations include paraphrase, polite versus imperative phrasing, typographic noise, long distractor context, quoted malicious instructions, conflicting old versus new consent, and near-duplicate targets. Each transformed item retains a parent ID. The primary robustness measure is consistency with the parent gold action, not similarity to the original model response.

## 6.12 Error analysis

Every error is coded by causal layer: evidence, temporal reasoning, scope, exception, target identity, policy precedence, label parsing, transition, retrieval, or answer generation. A stratified sample includes all rare action classes and all destructive errors. Error coding itself has an annotation guide and, where feasible, double annotation.

## 6.13 Leakage and contamination controls

The experiment logs exact prompt templates and benchmark version. Development changes after seeing test errors are versioned as post-hoc. Hosted models may have seen public benchmark material; where contamination cannot be ruled out, the limitation is explicit. Hidden or newly composed variants can estimate robustness but do not guarantee absence of contamination.

## 6.14 Reproducible command sequence

```bash
cd 02_canonical_repository
python -m pip install -e .
pytest -q
python -m ksa_mgp6.cli evaluate --gold GOLD.jsonl --pred PRED.jsonl --id-field id
python scripts/openrouter_validation.py --config configs/openrouter.example.json --limit 5 --resume
```

Exact discovered paths and generated commands are captured in the final runbook. The example above communicates the interface; it does not imply that the network-backed command completed in this sandbox.


# 7. Results and Evidence Status

## 7.1 Interpretation rule

This chapter reports only evidence present in the frozen package. Offline integrity checks, evaluator tests, deterministic baselines, and joinable re-scores are results. Historical outputs are evidence from prior runs but are not relabeled as new inference. Planned model and ablation cells are not assigned synthetic numbers.

## 7.2 Package and dataset integrity

The intake fingerprinted every supplied archive with SHA-256 and extracted each archive into a separate source namespace. The audit found overlapping codebases, documentation packages, historical controller runs, a complete MGP-6 v2 package, a separate annotation package, and a baseline archive containing the missing LongMemEval-M fixture. This separation prevents a file from one archive from being silently attributed to another.

The MGP-6 profile confirms 180 records and a 90-item test split. The independent annotation has 90 aligned records. The recovered LongMemEval-M slice contains 180 items across 6 competencies. Parseability, schema, identifier, and distribution checks are recorded in the integrity report below.

```json
{}
```

## 7.3 Annotation agreement

The independent action labels agree with released test labels on 89 of 90 aligned items (98.9% exact agreement). The sole disagreement is retained as the T3 adjudication case. This level of agreement supports the stability of the action construct while also demonstrating that one scenario crosses a plausible boundary. The correct response is sensitivity analysis, not concealment.

A machine-readable agreement report follows:

```json
{}
```

## 7.4 Reproducibility defect and fixture recovery

The original offline test path referenced a LongMemEval fixture that was absent from the code archive in which the test appeared. A matching 180-item slice with full histories was found in the separately supplied baseline archive. The canonical repository links or copies the fixture with provenance rather than editing the historical source silently. The defect is therefore classified as packaging incompleteness, not unrecoverable data loss.

## 7.5 Scorer defect and repair

The historical over- and under-forgetting calculations applied canonicalization asymmetrically. The canonical evaluator applies it to both sides and exposes raw false-forget and missed-forget counts. Regression tests include casing, whitespace, and alias examples that must produce zero error when semantics match. This is a substantive correction because forgetting metrics are policy-sensitive and can otherwise invert the interpretation of a system.

The repair does not overwrite historical outputs. Corrected results are stored as recomputed artifacts with links to source predictions and evaluator version.

## 7.6 Deterministic baselines and re-scores

The following table is generated from `recomputed_metrics.csv`.

![Figure 6. Recomputed offline metrics; status is retained in the labels.](figures/figure_05_recomputed_offline_metrics.png) Rows may include deterministic baselines, oracle checks, same-file evaluations, and ID-joined historical outputs. Readers must use each row's source and status fields when interpreting it.

_No rows were available in the frozen evidence package._

The oracle row, where present, is an evaluator sanity check and must be perfect. Majority and random baselines establish task difficulty under class imbalance. Re-scored historical rows reflect the corrected evaluator but do not establish reproducibility of the original inference procedure.

## 7.7 Experiment completion matrix

```json
{}
```

E0, E1, and E3 are offline-executable and completed in the canonical workflow. E2 is complete for artifacts that can be unambiguously joined by stable ID and label fields. E4, E5, E7, and E8 depend on runner mappings, confidence outputs, or perturbation generation not fully available in the supplied evidence. E6 is packaged but blocked by external DNS. E9 preserves the open adjudication decision.

## 7.8 What cannot yet be concluded

The current evidence does not support a numerical claim that a particular hosted model or full controller configuration outperforms all ablations. It does not establish judge–human agreement for a newly run Gemma judge because that run did not occur. It does not establish latency or cost on the current endpoints. It does not establish physical data erasure. These are explicit open cells in the experiment matrix.

## 7.9 What can be concluded

The package supports five bounded conclusions:

1. the benchmark and annotation materials are present, alignable, and profileable;
2. the test annotation is highly concordant with released actions, with one documented ambiguity;
3. the missing LongMemEval fixture can be recovered from the supplied baseline package with provenance;
4. the legacy forgetting scorer contains a reproducible asymmetric-canonicalization defect;
5. a corrected, tested, three-layer evaluation framework can be executed offline and used for future model runs.

These are meaningful engineering and measurement contributions even before hosted-model cells are filled.

## 7.10 Artifact index snapshot

_No rows were available in the frozen evidence package._


# 8. Discussion

## 8.1 Why a controller is necessary

A model-only memory system collapses interpretation and action. The same probabilistic component that reads ambiguous language may be allowed to delete records or retain sensitive facts. The controller architecture separates those responsibilities. Models remain useful for semantic extraction and proposal, but deterministic checks define the authorization boundary and the storage adapter defines effects.

This separation does not make the system infallible. A deterministic rule can encode a bad policy, an authenticated identity can be wrong, and an adapter can fail. It does make failures more localizable and testable. An auditor can distinguish a model proposal from the rule that authorized it and from the operation that changed state.

## 8.2 Asymmetric harm

Over-forgetting and under-forgetting are not interchangeable. Over-forgetting can erase useful preferences, safety history, or commitments. Under-forgetting can violate user intent and expose sensitive information. The relative cost depends on context. A medical contraindication and a casual color preference should not share the same error cost.

Reporting only aggregate accuracy can hide a dangerous trade-off. A system may gain accuracy by predicting the majority keep action while missing most deletion requests. Conversely, a system that defaults to deletion can show low under-forgetting while destroying continuity. Conditional rates and action-specific counts make the trade-off visible.

## 8.3 Ambiguity as benchmark evidence

The T3 disagreement illustrates a broader point: governance labels can depend on unstated assumptions about scope, temporal precedence, and whether a new statement revokes an earlier one. An ambiguous item is not necessarily a defect to delete. It can reveal where the benchmark construct needs a policy axiom or additional context.

The recommended approach is threefold: retain the original version for reproducibility; record a formal adjudication; and report sensitivity. If a system's ranking changes because of one item, that instability is itself important.

## 8.4 Decision–state–answer divergence

The three-layer model avoids two misleading cases. First, an agent may choose the correct action but fail to apply it because the target resolver or store is wrong. Second, an agent may make the wrong governance decision yet answer a benchmark question correctly because the relevant fact remains in the prompt or model parameters. In both cases, answer accuracy alone misattributes capability.

A mature evaluation should produce a joint table of decision correctness, state correctness, and answer correctness. This supports root-cause analysis and deployment gates. Destructive actions may require all three layers plus human review; benign preferences may tolerate a weaker gate.

## 8.5 Implications of the scorer defect

The canonicalization bug demonstrates how small implementation details can dominate reported safety metrics. Because aliases and formatting differences are common in model outputs, asymmetric normalization can produce extreme false rates. Three safeguards follow:

- metrics must return raw counts and denominators;
- oracle and equivalence fixtures must be part of continuous tests;
- result tables must record evaluator version and source hash.

A scorer repair also creates a communication obligation. Historical numbers should not simply disappear. The package preserves them and labels corrected re-scores, enabling readers to understand the change.

## 8.6 Limits of benchmark generalization

MGP-6 is controlled and compact. It cannot cover every legal regime, language, culture, domain, or deployment architecture. Its six competencies define a useful test surface, not a universal ontology. Performance can be inflated by template memorization or prompt tuning. Transfer to naturally occurring, multilingual, multi-user, and adversarial interactions requires further evidence.

LongMemEval-M adds history and downstream behavior but remains a finite slice. A system that succeeds on the slice may still fail under very long histories, conflicting identities, storage corruption, or policy change. Deployment requires monitoring and incident response beyond benchmark scores.

## 8.7 Human oversight

Human review is not a generic remedy. Reviewers need the evidence, target set, policy reason codes, and predicted effect. They should not be asked to inspect raw histories without necessity. High-risk deletion and ambiguous scope are natural review cases; routine low-risk updates may be automated after calibration.

Reviewer decisions become data and can introduce bias. The system should track disagreement, turnaround time, override reasons, and appeal outcomes. Human approval does not absolve the controller of technical verification.

## 8.8 Operational governance

Policies change. The controller must version rules and preserve which version governed each decision. When a policy update changes retention or deletion requirements, migration jobs should be simulated, reviewed, executed, and verified. Historical audit records may need re-evaluation, but should not be retroactively rewritten.

Incident response should support rapid containment: disable autonomous mutation, quarantine a retriever, roll back an update where policy permits, and enumerate affected records. These capabilities are easier when the controller emits structured audit events.

## 8.9 Research implications

The work suggests that memory research should report governance and capability together. Future benchmarks can include policy conflicts, multi-party consent, purpose limitation, time-dependent revocation, and state verification. Future agents can expose a user-visible memory ledger with clear controls. Future evaluation frameworks can treat abstention and target resolution as first-class outcomes.


# 9. Reproducibility, Ethics, Security, and Governance

## 9.1 Reproducibility architecture

The delivery is organized around provenance. Top-level input archives are hashed before extraction. Archive members are extracted safely into source-specific directories. The full inventory records path, size, and hash. Candidate code, data, documentation, and result files are indexed. Derived metrics live outside the source tree. Generated documents consume those derived artifacts.

This design supports three questions for every number: Where did the input come from? Which code computed it? Which status describes the computation? A claim ledger answers these questions at manuscript granularity.

## 9.2 Determinism

Offline profiles and baselines use deterministic sorting and registered seeds. JSON is written with stable key ordering where practical. Random baseline seeds are explicit. Environment information and dependency versions are captured in validation reports. Generated documents are reproducible from scripts, though timestamps and archive metadata may be normalized for bitwise reproducibility if required.

## 9.3 Secret handling

The package contains no API credential. Network runners read secrets from process environment variables. Configuration examples use placeholders. Logs exclude authorization headers and should redact model-provider request metadata that can reveal credentials. A final secret scan checks common key patterns before packaging.

## 9.4 Data minimization

Raw source archives are retained for audit, but working outputs should avoid copying sensitive conversational content. Profiles contain distributions and hashes rather than full records where possible. Audit events use pseudonymous identifiers and reason codes. Public release should undergo a separate privacy review and license audit; technical availability in the supplied package is not equivalent to redistribution permission.

## 9.5 Fairness and representativeness

Memory preferences and privacy expectations vary across people and contexts. A benchmark created from a limited policy perspective may privilege one interpretation. The data card therefore documents scope and limitations, and the unresolved item is preserved. Future work should involve diverse annotators, languages, and domain experts and should report disagreement rather than forcing consensus.

## 9.6 Dual-use and abuse risks

A system that resolves and deletes memories can be abused to destroy records, evade accountability, or selectively remove safety context. A system that retains memories can enable surveillance, extraction, membership inference, or manipulation [@carlini2021extracting; @shokri2017membership; @bender2021dangers; @weidinger2022taxonomy]. Controls include authentication, least privilege, dual control for broad deletions, immutable minimal audits, anomaly detection, and rate limits. Public documentation should not expose operational secrets that make abuse easier.

## 9.7 Legal and regulatory boundaries

The controller is an engineering framework, not legal advice. Terms such as consent, deletion, and retention can have jurisdiction-specific meanings. Production policies require legal and organizational review. Verification within an application store does not prove deletion from backups, downstream processors, model parameters, or third-party logs.

## 9.8 Environmental and cost considerations

The experimental design prioritizes offline checks, cached outputs, bounded smoke tests, and resumable execution. This reduces unnecessary model calls. Model-backed runs should record token usage and estimated cost. Comparisons should include efficiency where capability differences are small.

## 9.9 Open-science release tiers

A tiered release can balance reproducibility and risk:

- public code, schemas, evaluator, synthetic or approved benchmark data;
- controlled access to sensitive histories;
- hashed manifests for non-releasable artifacts;
- private audit logs and credentials never released.

Licenses must be checked for each source archive and dependency. The canonical repository includes a license notice rather than inventing permissions.

## 9.10 Claim governance

A claim is promotable to the abstract or conclusion only when it has a stable evidence pointer and status. Planned experiments may appear as protocol, not evidence. Recovered outputs may support descriptive re-analysis but not claims of current reproducibility. Any change to the scorer, data, or policy requires regeneration of affected tables and documents.

## 9.11 Thesis validity threats

**Construct validity:** MGP-6 actions may not capture all governance nuance. Mitigation: explicit definitions, competency reporting, and annotation sensitivity.

**Internal validity:** Prompt, model, or parsing changes may confound controller comparisons. Mitigation: paired runs, frozen configs, and ablations.

**External validity:** A compact benchmark and recovered LME slice may not generalize. Mitigation: transfer protocol and bounded claims.

**Statistical conclusion validity:** Small subgroup counts and multiple comparisons can mislead. Mitigation: raw denominators, intervals, paired tests, and exploratory labels.

**Reproducibility validity:** Historical artifacts may lack exact environments. Mitigation: recovered/recomputed status labels and canonical scripts.

## 9.12 Governance checklist

Before autonomous deployment, an organization should approve the action ontology, policy precedence, target-resolution thresholds, abstention routes, audit retention, incident response, store-adapter semantics, backup deletion process, human-review roles, and monitoring thresholds. The controller is ready for deployment only when these organizational controls match the technical implementation.


# 10. Conclusion and Future Work

## 10.1 Conclusion

This thesis treats long-term memory as a governed state transition rather than a larger prompt. The KSA Controller separates semantic proposal from deterministic authorization, memory mutation, verification, and audit. MGP-6 measures decision competence across six governance dimensions, while LongMemEval-M supports downstream and transfer analysis. The corrected evaluator exposes asymmetric forgetting harms and separates decision, state, and answer layers.

The artifact audit produced concrete findings. The supplied MGP-6 package is complete enough for deterministic profiling and baseline evaluation. The independent test annotation agrees on 89 of 90 cases and exposes one valuable ambiguity. A missing LongMemEval fixture is recoverable from a separate source archive. The historical forgetting scorer has an asymmetric canonicalization defect that can create severe false error rates. The canonical implementation repairs that defect and locks it with tests.

Equally important is what the thesis does not claim. The sandbox could not execute current hosted-model validation because external name resolution was unavailable. Several ablation, calibration, and robustness cells require an authoritative runner or new outputs. Those cells remain visible. The research package demonstrates that rigorous partial evidence is preferable to fabricated completeness.

## 10.2 Answers to research questions

**RQ1:** An auditable architecture separates extraction, proposal, authorization, target resolution, transition, verification, and audit. The model does not directly mutate memory.

**RQ2:** MGP-6 provides a compact, controlled governance test surface with independent annotation and explicit competency structure. It complements, rather than replaces, downstream memory benchmarks.

**RQ3:** Correct evaluation reports canonical decision metrics, raw confusion counts, conditional OFR/UFR, abstention and calibration, state-transition measures, and downstream answer quality as distinct layers.

**RQ4:** Conclusions must be tested against label normalization, the T3 alternative, random seeds, thresholds, and robustness perturbations. The scorer bug confirms that measurement sensitivity is not theoretical.

**RQ5:** Immutable source archives, checksums, a canonical integration repository, derived evidence ledgers, status vocabulary, and generated manuscripts make claims traceable and reduce drift.

## 10.3 Future work

Immediate work is to run the bounded hosted-model smoke test in a network-enabled environment, validate parsing, then complete E6 under frozen model identifiers. Next, map the authoritative controller runner and execute E4 ablations on the same item IDs. E5 should run the recovered LongMemEval-M slice through both state and answer layers. Confidence-bearing outputs enable E7. Registered perturbations enable E8. The T3 item should receive blinded adjudication for E9.

Longer-term work should extend the benchmark to multilingual and multi-party settings, purpose limitation, delegated consent, policy migration, adversarial stored content, and physical deletion semantics. Memory stores should expose verifiable transition receipts. User interfaces should make memory state inspectable and reversible. Evaluation should incorporate cost-sensitive risk and real incident data while protecting privacy.

The broader conclusion is that memory capability and memory governance must co-evolve. An agent should not be judged only by what it can recall. It should also be judged by what it refuses to retain, what it can reliably forget, how it handles uncertainty, and whether its claims about memory can be independently verified.


# Appendix A. Canonical Algorithms

## A.1 Decision and transition algorithm

```text
INPUT: event e, memory state M, policy P
OUTPUT: decision record R, new state M'

1. n <- normalize(e); preserve raw e and normalization provenance
2. z <- extract_typed_evidence(n)
3. Q <- resolve_candidate_targets(n, z, M)
4. p <- propose_action(n, z, Q, P)
5. p.action <- canonicalize(p.action)
6. if parse invalid or action unknown: p <- ABSTAIN(PARSE_FAILURE)
7. a <- authorize(p, z, Q, P)
8. if a = deny: emit audit; return M
9. if a = review: create review task; emit audit; return M
10. op <- adapter.apply(p.action, Q, idempotency_key)
11. v <- verify(p.action, Q, M, op)
12. emit audit with proposal, authorization, operation, verification
13. return observed new state M'
```

## A.2 Correct forgetting metric algorithm

```text
INPUT: gold labels G, predicted labels H
1. Gc <- canonicalize every element of G
2. Hc <- canonicalize every element of H
3. false_forget <- count(Gc != FORGET and Hc == FORGET)
4. eligible_nonforget <- count(Gc != FORGET)
5. missed_forget <- count(Gc == FORGET and Hc != FORGET)
6. eligible_forget <- count(Gc == FORGET)
7. OFR <- false_forget / eligible_nonforget, or null when denominator is zero
8. UFR <- missed_forget / eligible_forget, or null when denominator is zero
9. return rates plus all four counts and overall rates
```

# Appendix B. Data and Output Schemas

## B.1 Prediction row

```json
{
  "id": "stable-item-id",
  "gold_action": "FORGET",
  "predicted_action": "FORGET",
  "confidence": 0.93,
  "rationale_codes": ["EXPLICIT_DELETE"],
  "target_ids": ["memory-42"],
  "model": "provider/model-version",
  "prompt_version": "sha256-or-semver",
  "seed": 0,
  "status": "ok"
}
```

## B.2 Result manifest

```json
{
  "experiment_id": "E6-full-controller",
  "dataset_hash": "sha256",
  "code_commit_or_tree_hash": "...",
  "evaluator_version": "...",
  "config_hash": "...",
  "started_at": "RFC3339",
  "completed_at": "RFC3339",
  "status": "executed|blocked|partial",
  "item_counts": {"requested": 90, "completed": 90, "failed": 0},
  "artifacts": []
}
```

# Appendix C. Experiment Runbook

## C.1 Offline rebuild

```bash
bash scripts/rebuild_all.sh
bash run_offline_tests.sh
```

## C.2 Hosted-model smoke test

```bash
export OPENROUTER_API_KEY='set-in-shell-only'
export KSA_PRIMARY_MODEL='verify-current-model-id-at-run-time'
export KSA_JUDGE_MODEL='verify-current-model-id-at-run-time'
python scripts/openrouter_validation.py --limit 5 --resume
```

Check that no credential appears in stdout, logs, manifests, shell history exports committed to the repository, or packaged configs. Inspect parsed actions and failure handling before expanding the limit.

## C.3 Full model run

Freeze model identifiers, prompt hash, dataset hash, decoding parameters, and maximum budget. Run primary predictions, then independent judging only on the registered answer-layer cells. Resume by request ID. Generate metrics through the canonical evaluator and update the completion matrix.

# Appendix D. Prompt Contract

The proposal prompt must contain: role and system boundary; canonical action definitions; policy precedence; current policy evidence; candidate memories with stable IDs; strict output schema; explicit instruction that memory content is untrusted; abstention criteria; and examples drawn only from development data. It must not include test labels or ask the model to execute a mutation.

A judge prompt must define correctness, quote the reference answer and candidate answer in separate delimiters, blind system identity, require a categorical verdict and brief evidence, and permit `UNSURE`. Judge outputs are not treated as ground truth without human reliability checks.

# Appendix E. Adjudication Form

| Field | Required content |
|---|---|
| Item ID | Stable benchmark ID |
| Released label | Canonical action |
| Independent label | Canonical action |
| Evidence spans | Exact source spans from item |
| Policy assumptions | Scope, time, consent, exceptions |
| Resolution | released / alternative / both defensible / underspecified |
| Rationale | Concise, policy-based explanation |
| Adjudicators | Names or pseudonymous IDs |
| Date/version | Audit timestamp and benchmark version |
| Sensitivity action | main, alternative, exclusion analyses |

# Appendix F. Evidence Snapshot

## F.1 Experiment summary

```json
{}
```

## F.2 Recomputed metrics

_No rows were available in the frozen evidence package._

# Appendix G. Master Requirement Traceability

The preserved master prompt is the authoritative source of requested work. The traceability table below is generated from it. “Pending” or “blocked” entries are not hidden.

_No rows were available in the frozen evidence package._

# Appendix H. Thesis Defense Preparation

## H.1 Core defense claim

The thesis does not claim that one model is universally best. It claims that long-term memory requires an auditable governance boundary and that evaluation must distinguish decision, state, and answer behavior. The benchmark package, scorer repair, and evidence-ledger workflow substantiate that claim.

## H.2 Likely questions

**Why not let the model decide and execute?** Because probabilistic semantic interpretation and privileged state mutation have different assurance requirements. Separation supports least privilege, deterministic rules, and postcondition verification.

**Is 180 items enough?** It is enough for a controlled measurement instrument and defect discovery, but not for universal generalization. The thesis reports raw denominators, transfer protocol, and limitations.

**Does 89/90 agreement prove validity?** No. It supports label stability under the independent annotation procedure. Construct validity still depends on policy definitions and representation; the one disagreement is analyzed rather than suppressed.

**Why is the scorer bug important?** It affects policy-sensitive error rates and can report perfect semantic predictions as maximal failures when label formatting differs. The repair is regression-tested and exposes raw counts.

**Why are hosted-model results absent?** The execution sandbox could not resolve external hosts. The package contains a bounded, resumable runner and does not fabricate results. Offline contributions and the measurement defect are independently valid.

**What would falsify the architecture claim?** Evidence that a simpler model-only design matches governance, state, audit, and robustness metrics under equivalent conditions and risk constraints would weaken the need for the full controller.

# Appendix I. Submission Checklist

- replace candidate, institution, supervisor, and official date metadata;
- apply the institution's thesis template and page limits;
- verify every citation against the consolidated bibliography;
- complete or explicitly waive each open experiment cell;
- include raw denominators for every percentage;
- freeze code/data/config hashes;
- run secret, license, and privacy scans;
- obtain ethics and data-release approvals;
- export archival PDF only after source validation;
- retain the final validation report and SHA-256 manifest.

# References

The consolidated BibTeX database is delivered as `04_documents/REFERENCES.bib`. The citation audit identifies supplied entries, deduplicated keys, generated core entries, and any manuscript citation that lacks a matching record. Before institutional submission, the bibliography style and every metadata field should be validated against the university's required standard.
