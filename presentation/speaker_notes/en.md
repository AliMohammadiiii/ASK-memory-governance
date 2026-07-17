# Speaker notes — English defense

## 1. Governing Long-Term Memory Before Retrieval

Open with the research question: can a memory system decide whether a new claim should be committed, replace an older claim, or be refused? Preview that the thesis evaluates this decision directly, not only downstream answer accuracy.

## 2. Long-term memory is a mutable state, not a document collection

Frame memory as an epistemic state. The key risk appears before retrieval: a bad write can remain active and influence many future answers.

## 3. Retrieval-only pipelines leave the write decision implicit

Contrast the two abstractions. This thesis does not argue retrieval is unnecessary; it argues retrieval begins after a governance decision has already shaped the state.

## 4. The research gap is a missing, measurable write boundary

State the narrow gap. Avoid primacy claims: related systems contain update actions, versioning, and abstention-like ideas. The contribution is the operationalized combination and layered evaluation.

## 5. The policy fixes three write actions and their state semantics

Define each action precisely. Stress that ABSTAIN is a no-mutation safety action, not an answer-level refusal, and that SUPERSEDE preserves the old record for audit.

## 6. KSA places model proposals inside a deterministic governance boundary

Walk left to right. Extraction and relation classification can be model-assisted; the action vocabulary, no-mutation behavior, lineage update, and active-only retrieval remain deterministic invariants.

## 7. The interpretable controller uses two scores and an ordered decision rule

Explain the ordered rule. Abstention is evaluated first. Supersession also requires contradiction pressure, so a high score alone cannot deactivate a prior record.

## 8. Lineage makes revision reversible and auditable

Describe lineage as a state invariant, not a decorative log. Normal retrieval excludes inactive records, while explicitly historical questions can still inspect the chain.

## 9. MGP-6 isolates the write decision across six conflict types

Position MGP-6 correctly: it is a controlled diagnostic, not a community benchmark or population sample. Its role is causal localization of write-policy behavior.

## 10. The protocol separates result status and evaluation layer

This is the methodological core. Separating layers prevents a downstream answer score from hiding unsafe writes or a decision score from hiding broken lineage.

## 11. Structured governance reaches the strongest MGP-6 decision accuracy

Lead with the completed full-corpus results. The safest inferential contrast is structured rule governance versus the unstructured zero-shot decision baseline. Do not claim the rule policy beats the LLM policy statistically.

## 12. The rule controller’s remaining errors are conservative

Interpret the error direction. The controller sometimes fails to update under weak evidence, but it does not commit a false write on any gold-ABSTAIN item in this diagnostic.

## 13. Ablations attach a distinct failure signature to each component

Use this slide to justify each component. The no-lineage row is especially important: action labels stay unchanged while the stored-state audit property collapses.

## 14. External-system scores depend strongly on how NOOP is mapped

Explain why adapter comparisons need two mappings. These values describe behavior under the harness interface, not the systems’ full native capabilities.

## 15. Annotation evidence is strong but comes from one independent annotator

Be precise about annotation. There is one independent annotator, not a multi-human panel. The four-model agreement study is a model audit and must never be described as human inter-annotator agreement.

## 16. LongMemEval has no final result—and the 77.2% construction is rejected

Treat this as a negative-result slide. The decisive top-up found 13 regressions among 84 previously successful items. Even the most favorable bound cannot reach 77.2 percent.

## 17. Single-session preference remains the hardest downstream competency

Emphasize that no SSP failure was traced to the governance decision policy. The dominant mechanisms are retrieval ranking and answer realization, which demonstrates why layered evaluation matters.

## 18. The error analysis separates safety failures from coverage failures

Tie each observed failure to a distinct layer. This is stronger than a single aggregate score because it tells us what intervention would actually address the failure.

## 19. The conclusions are deliberately bounded

Do not rush this slide. The thesis makes a narrow supported claim and preserves null and negative findings. These limitations define the next experiments rather than invalidating the controlled diagnostic.

## 20. Govern the write; then evaluate the state and the answer

Close by answering the research question: an interpretable governed write path can make memory revision explicit and measurable, but the evidence supports a controlled diagnostic claim, not a final downstream superiority claim.

## 21. Backup — formal decision and failure definitions

Use this backup if asked for notation or metric definitions. Clarify that premise resistance and invalid-commit rate are project-defined diagnostic metrics.

## 22. Backup — baseline mechanisms and what each can express

Use when a committee member asks whether baselines are capability-matched. They are reference mechanisms designed to isolate memory policies, not broad system rankings.

## 23. Backup — statistical tests and inferential scope

Mention exact paired two-sided McNemar tests, Holm correction across the prespecified family, and paired risk differences. No LongMemEval hypothesis test is valid for the incomplete heterogeneous evidence.

## 24. Backup — annotation agreement and the single boundary case

The disagreement sits on the same SUPERSEDE/ABSTAIN boundary as the controller’s conservative errors. It is retained with an explicit blinded-adjudication protocol.

## 25. Backup — leakage controls and researcher degrees of freedom

Use this slide to answer leakage concerns. The largest researcher degree of freedom was the LongMemEval failure-replay construction; the audit explicitly rejects it and preserves the contradiction from the complementary top-up.

## 26. Backup — why the LongMemEval evidence is diagnostic only

Explain selection bias visually. Replaying only failures and retaining all old successes can inflate the merged score. The top-up directly tests that assumption and finds regressions.

## 27. Backup — external action mappings

Use this table if asked for exact adapter values. Repeat that both mappings are disclosed and MemOS is not included as a final-candidate capability result.

## 28. Backup — nearest conceptual neighbors narrow the novelty claim

State the allowed novelty claim: operationalization and controlled layered evaluation of this combination. Do not claim invention of update actions, abstention, lineage, provenance, or memory governance.

## 29. Backup — ethical and deployment risks

Clarify that governance here is epistemic, not a legal-compliance guarantee. Deployment requires organizational access control and privacy policy beyond this research prototype.

## 30. Backup — additional complete MGP-6 results

The six-shot row is coverage-aware: six missing predictions are aligned as INVALID. It remains incomplete and is excluded from completed-run inferential comparisons.

## 31. Backup — architecture and code ownership follow the evaluation layers

Point to the repository structure if implementation questions arise: src/ksa contains the library; scripts contain frozen runners and verification; benchmarks contain the redistributable MGP-6 diagnostic; artifacts and reports contain ledgers and audit outputs.
