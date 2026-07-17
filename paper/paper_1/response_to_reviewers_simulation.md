# Response to reviewers (simulation)

This document rehearses the strongest objections after the diagnostic-paper
rewrite. It is not part of the submission.

**1. “The controller and dataset were designed by the same authors.”**

Agreed. We no longer use MGP-6 v2 to claim method superiority. The manuscript
leads with the failed shortcut gate: conflict type alone obtains perfect held-out
accuracy. We frame the existing set as a pilot for exposing measurement failure
and provide a role-separated successor protocol. Addressed in the abstract,
§4, §7.1, and §9.

**2. “The held-out split still leaks the label.”**

Correct. Family-disjoint splitting prevented exact template-family reuse but
did not break the conflict/type-to-action mapping. The conflict-only and
type-only probes are now primary results. Addressed in §4.4, §6, Table 1, and
§7.1.

**3. “The structured LLM is numerically better than the rule policy.”**

Correct on this test: 0.9000 versus 0.8889. The paired family-cluster interval
includes zero, so we claim neither superiority nor non-inferiority. Addressed in
the abstract, §7.2, and Table 2.

**4. “Zero false commits is being sold as safety.”**

It is not. We report 0/33 action false commits with a one-sided 95% upper bound
of 0.0868, alongside the 10/45 missed-update count. Cost-sensitive analysis
shows that the preferred system changes between commit-averse and
update-responsive regimes. Addressed
in §7.3 and §9.

**5. “The paper describes a scorecard that did not produce the results.”**

The mismatch is corrected. §5 describes the actual deterministic lexical
reference policy and explicitly notes that the broader prototype’s weighted
five-feature scorecard did not generate these predictions and is not evaluated
by this experiment.

**6. “A single-step synthetic set is not long-lived memory.”**

Agreed. We restrict v2 to transition-level diagnostics. The prospective v3
protocol requires 5/10/20-turn trajectories, A→B→C and A→B→A patterns, delayed
evidence, multiple slots, and leave-one-family-out analysis. Addressed in §9 and
the public protocol.

**7. “One human annotator plus LLM judges is not human IAA.”**

Agreed. The two sources are reported separately. The manuscript does not use
“multi-human inter-annotator agreement.” V3 requires three blinded humans and
preserves pre-adjudication labels.

**8. “External systems are evaluated through an unfair mapping.”**

Mapped external-system action rankings are removed from the main paper. V3
requires native observable operations for primary comparisons and permits
action mapping only as a fully disclosed sensitivity analysis.

**9. “The downstream evidence is contaminated or incomplete.”**

Agreed. The LongMemEval section and table are removed from the main manuscript.
The artifacts remain only for provenance and failure analysis. A downstream
claim is gated on one complete, homogeneous, no-carry-forward run.

**10. “Why is this publishable after conceding so much?”**

The paper’s contribution is an auditable evaluation decomposition and a concrete
negative result about how an apparently strong held-out memory-governance score
can be reproduced by label shortcuts. It also releases per-item predictions,
cluster-aware analysis, asymmetric error metrics, and a falsifiable successor
protocol. We do not ask the pilot to support claims it cannot identify.
