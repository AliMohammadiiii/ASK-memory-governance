# Response to reviewers (simulation)

Updated 2026-07-27. This document rehearses the strongest objections to the
current MGP-6 v4.3 and LongMemEval V12 manuscript. It is not part of the
submission.

**1. “The authors designed the diagnostic, labels, and controller.”**

That criticism invalidates a broad capability claim, especially for the v2
pilot, where conflict type perfectly predicts the held-out action. The paper
now treats v2 as a construct-validity failure. V4.3 breaks the measured mapping
by putting all three actions inside each semantic component, isolating
components across splits, and enforcing duplicate and restricted-view shortcut
gates. It remains an owner-designed controlled diagnostic, not a population
benchmark or independent deployment test.

**2. “You compared many systems after looking at the hidden set.”**

We did not. Only the single frozen composed controller was authorized on the
sealed v4.3 hidden split. Every baseline, ablation, successor, external-system,
and component comparison is explicitly development-only. The paper does not
use development contrasts to claim hidden improvement.

**3. “The five-feature scorecard did not produce the headline v4.3 result.”**

Correct, and the mechanisms are separated throughout. The scorecard produced
all 12,654 LongMemEval V12 write decisions; the v2 artifact used a lexical
policy; the v4.3 hidden run used a composed model--public-evidence controller.
The scorecard's v4.3 development adapter obtains 0.3333. The paper claims
runtime transparency and mechanism diagnosis for the scorecard, not v4.3
write-label superiority.

**4. “Exact scorecard replay does not show that its writes are correct.”**

Correct. Exact replay proves execution fidelity. LongMemEval supplies no gold
action for each extracted candidate, so the dimension and guard
counterfactuals establish rule dependence, not correctness, causal benefit, or
threshold optimality. The downstream QA comparison is reported as a separate
outcome.

**5. “The advertised five dimensions are effectively only two.”**

On the observed V12 support, marker burden controls abstention and signed
relation controls supersession. Omitting confidence changes eight actions;
omitting evidence quality or the stability prior changes none. Common
type-specific thresholds change only five. We report this effective
dimensionality as a result, not hide it, and describe the unused channels as
hand-specified policy commitments that need independent calibration.

**6. “The weighted supersession score is unsafe without an ad hoc guard.”**

The discrete negative-relation guard is indeed load-bearing. Removing it
changes 11,091 KEEP decisions to SUPERSEDE because 96.6% of observed KEEP
scores already clear the scalar supersession threshold. The paper therefore
defines the controller as an ordered score-plus-guard rule and identifies the
guard as the safety-critical mechanism.

**7. “The composed v4.3 controller’s gain may come from only one component.”**

The response trace records the model proposal, public-evidence rule proposal,
and final action. On development, neither component reaches the composed
accuracy. The conservative guard repairs 37 model errors and introduces 9,
which localizes the benefit to their composition. No analogous component claim
is made on hidden because component scoring there was not authorized.

**8. “The LongMemEval gain could come from a deterministic answer solver rather
than memory writes.”**

The answer-layer computation aid is separately traced. No V12 item bypassed the
answer model. It replaced two controller answers under verification: one repair
and one regression, for zero net accuracy change. The 23-item aggregate
controller advantage over naive overwrite therefore cannot be explained by
deterministic output substitution.

**9. “The cost comparison hides the expensive parts of the pipeline.”**

The paper reports extraction, relation classification, and answer generation
separately. In V12, write-time ingestion consumes 92.8% of prompt tokens and
99.4% of model calls; answer generation is 7.2% of prompt tokens. Latency is
identified as provider-reported route time, not hardware compute, and monetary
cost is unavailable rather than imputed from list prices.

**10. “External memory systems are unfairly forced into your action labels.”**

External rows are development-only and retain their adapter/mapping
qualification. They are not treated as native operation comparisons or hidden
evidence. The manuscript makes the mapping dependence part of the result
boundary.

**11. “The downstream evidence is contaminated or selection-biased.”**

The older v7 and 77.2% carry-forward artifacts are explicitly ineligible. The
paper's downstream claim uses the homogeneous V12 180-item slice with one
answer model and one judge. Two provenance-bookkeeping issues remain disclosed:
a stale launcher hash and a manifest not finalized after resume. Neither changes
the recorded predictions, but both prevent a stronger clean-room claim.

**12. “The ingredients already exist in prior memory systems.”**

They do. The paper claims no priority for memory write actions, abstention,
typing, provenance, lineage, operation-level evaluation, or the phrase
“memory governance.” The narrower contribution is the executable conjunction:
write-, state-, lineage-, retrieval-, and answer-layer outcomes remain
separately observable; the deployed write rule is exactly replayable; its
effective mechanism is measured by dimension, type, and guard; and a controlled
diagnostic is paired with downstream evidence under explicit validity
boundaries.
