# Thesis Defense Questions and Concise Answers

## Problem and contribution

1. **What problem does the thesis solve?**  
   It makes persistent-memory writes explicit and auditable by deciding KEEP, SUPERSEDE, or ABSTAIN before mutation.

2. **What is the thesis's core contribution?**  
   Operationalizing and evaluating a combined three-action write policy at decision, stored-state/lineage, and downstream-answer layers.

3. **What is not novel here?**  
   Updating, versioning, provenance, lineage, abstention, gating, and operation-level evaluation all have prior art.

4. **Why avoid a “first” claim?**  
   The literature contains close precedents for every constituent mechanism, and the evidence does not justify priority for the conjunction.

5. **Why is this governance rather than ordinary memory management?**  
   The action is policy-constrained, side-effecting, reviewable, and tied to provenance and lineage rather than being an opaque storage heuristic.

6. **Why three actions?**  
   KEEP handles compatible information, SUPERSEDE handles justified replacement, and ABSTAIN prevents unsupported mutation.

7. **Why not use DELETE?**  
   Supersession preserves the prior record and lineage for audit; silent deletion destroys evidence.

8. **Why is ABSTAIN a write action if it does not mutate state?**  
   It is a policy outcome at the write boundary and records that evidence was insufficient to authorize mutation.

9. **Why use an interpretable rule policy?**  
   It makes thresholds and features inspectable and supports causal ablation without model-internal explanations.

10. **Could an LLM implement the same policy?**  
    Yes. The project includes an LLM-backed controller inside the same action and transition scaffold.

## Diagnostic design

11. **What is MGP-6 v2?**  
    An author-designed 180-scenario diagnostic slice covering six conflict types and three probe modes.

12. **Is MGP-6 a benchmark?**  
    It is a controlled diagnostic, not an independent community benchmark.

13. **What is the gold-action distribution?**  
    90 SUPERSEDE, 66 ABSTAIN, and 24 KEEP.

14. **Why is the distribution imbalanced?**  
    The diagnostic emphasizes governance-critical supersession and abstention behaviors that naive systems cannot express.

15. **What are the splits?**  
    60 train, 30 development, and 90 test.

16. **Why lead with test-split numbers?**  
    The rule policy was developed using train/development, so test-first reporting limits researcher flexibility.

17. **What do the query modes measure?**  
    Direct recall, resistance to stale premises, and implicit use of current state.

18. **How were labels audited?**  
    One independent annotator covered the 90 test items, plus a separate four-model audit panel.

19. **Can you claim human inter-annotator agreement?**  
    No. There is one independent human annotator, not multiple human annotators.

20. **What was the annotation disagreement?**  
    One implicit-conflict item, `MGP6V2-T3-TEST-016`, was gold SUPERSEDE and annotator ABSTAIN.

## Results and statistics

21. **What is the most important quantitative result?**  
    Conflict type alone reaches 1.000 held-out accuracy; type alone reaches 0.9667. The pilot fails its construct-validity gate.

22. **What are the held-out policy results?**  
    Reference: 0.8889 accuracy / 0.9145 macro-F1; structured LLM: 0.9000 / 0.9040.

23. **Does the reference policy beat or match the LLM?**  
    No such claim is licensed. The LLM is numerically higher and the paired family-cluster interval includes zero; that is neither superiority nor non-inferiority.

24. **Why is an item holdout insufficient?**  
    The conflict/type-to-action mapping persists across splits, so a system can recognize scenario categories without reasoning over evidence.

25. **What does zero observed action false commit mean?**  
    It is 0/33 test cases, not zero population risk; the one-sided 95% upper bound is 0.0868.

26. **What is the cost of the conservative reference policy?**  
    It misses 10/45 required updates, versus 7/45 for the structured LLM.

27. **Why use cluster bootstrap?**  
    Items share template and minimal-pair structure; resampling families better reflects dependence than treating 90 items as independent.

28. **Do the cost matrices select one universal winner?**  
    No. Commit-averse costs favour the reference, while update-responsive costs favour the structured LLM.

29. **What is action false-commit rate?**  
    Among gold-ABSTAIN items, the fraction predicted KEEP or SUPERSEDE. It is separate from state invalid-commit, which checks whether state mutated.

30. **Why report macro-F1 with accuracy?**  
    The action distribution is imbalanced, and macro-F1 gives each action equal weight.

## Ablations and causal interpretation

31. **What happens without abstention?**  
    Accuracy falls to 0.5556 and invalid-commit rate rises to 1.0.

32. **What happens without provenance?**  
    Accuracy falls to 0.7000 and invalid-commit rate rises to 0.606.

33. **What happens without typing?**  
    Macro-F1 falls to 0.5680 and KEEP F1 becomes 0.0.

34. **What happens without lineage?**  
    Action accuracy stays 0.9222 while lineage integrity falls from 0.8556 to 0.3689.

35. **Why is the lineage ablation important?**  
    It demonstrates within this generator that unchanged action labels can coexist with degraded lineage state; independent confirmation is still required.

36. **Do the ablations prove deployment safety?**  
    No. They attribute effects within this scaffold and diagnostic only.

## External systems and incomplete evidence

37. **How should external-adapter results be interpreted?**  
    As harness- and mapping-specific measurements, not native-system capability rankings.

38. **Why disclose both NOOP mappings?**  
    NOOP is not semantically identical to ABSTAIN, so the mapping changes accuracy materially.

39. **Why is MemOS diagnostic-only?**  
    Its adapter does not expose whether an old memory was replaced, making supersession unobservable.

40. **What is the few-shot baseline result?**  
    With 174/180 predictions and six missing scored INVALID, its coverage-aware bound is 0.7833 accuracy / 0.7692 macro-F1.

41. **Why is the few-shot row incomplete?**  
    Six required item predictions are absent; denominator alignment does not turn missing inference into a complete run.

## LongMemEval integrity

42. **What happened in LongMemEval v7?**  
    Provider failures produced 316 HTTP-402 traces and 388 empty extraction fallbacks, contaminating the run.

43. **Which v7 system scored higher?**  
    Naive overwrite scored 114/180, above the controller's 110/180, but both are diagnostic-only.

44. **Why is replaying prior failures biased?**  
    Selection depends on the earlier outcome, so the changed configuration and judge apply only to hard items.

45. **What did the failure replay observe?**  
    It repaired 25 of exactly 70 selected v7 failures; it is `failure_replay_only`.

46. **Why is the archived 139/180 construction excluded?**  
    It carries all prior successes forward, mixes regimes, selects failures for repair, and adds four post-hoc analyst overrides.

47. **What does the Modal top-up show?**  
    Among 84 observed prior successes, 71 stayed correct and 13 regressed, invalidating automatic carry-forward.

48. **What are the defensible combined bounds?**  
    There are 96/154 raw observed correct; unresolved items give full-180 raw bounds of 53.3%–67.8%.

49. **What happened to SSP?**  
    v7 was 11/30, the selected replay repaired 0/19 failures, and the top-up observes 8/29 with a maximum of 9/30; the values cannot be carried across versions.

50. **Why does the replay not isolate the answer model?**  
    Replay prompt contexts differ from v7, so multiple pipeline factors changed.

51. **What is the status of final-1.1?**  
    `externally_pending`; the supplied OpenRouter credential returned HTTP 403 before inference.

52. **Can you claim any final LongMemEval accuracy?**  
    No. Current rows are diagnostic-only, failure-replay-only, incomplete, invalid, or externally pending.

## Validity, ethics, and future work

53. **What is the main internal-validity threat?**  
    The author co-designed scenarios, gold policy, and rule features, making some baseline comparisons partly tautological.

54. **What is the main external-validity threat?**  
    One author-designed slice, one main model family, and one seed do not establish broad generalization.

55. **What is the main construct-validity threat?**  
    Bespoke metrics and a single independent human annotator require wider external validation.

56. **What is the main statistical-validity threat?**  
    Small diagnostic strata and the absence of run-to-run variance estimates.

57. **How does the system handle ambiguous writes?**  
    ABSTAIN produces no mutation and routes the case for review.

58. **What ethical risk does lineage create?**  
    Retaining superseded history can increase privacy and surveillance risk, so access control and retention policy are still required.

59. **What experiment should run next?**  
    The frozen homogeneous final-1.1 full-180 LongMemEval evaluation with an authorized provider credential.

60. **What would weaken the thesis's central claim?**  
    Evidence that a simpler design matches decision, state/lineage, audit, and answer behavior under equivalent risk constraints would reduce the need for the combined controller.
