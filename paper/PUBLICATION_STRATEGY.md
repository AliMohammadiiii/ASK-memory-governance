# Publication strategy

Updated: 2026-07-15.

## Paper identity

Submit this work as a **diagnostic/evaluation paper**, not a method-superiority
or leaderboard paper. The defensible contribution is:

1. a three-layer evaluation of write decision, stored state/lineage, and later
   answer behavior;
2. an explicit KEEP/SUPERSEDE/ABSTAIN decision problem with asymmetric costs;
3. a reproducible construct-validity audit showing that the current
   author-designed MGP-6 v2 pilot leaks labels;
4. a negative, useful result: the transparent rule policy does not beat the
   structured LLM on held-out test, and zero observed action false commits trades off
   against missed updates.

The title, abstract, results order, discussion, and conclusion must preserve
this identity. Do not describe the lexical reference policy as a learned or
weighted scorecard; the implemented five-feature scorecard did not generate the
reported MGP-6 predictions.

## Eligible main-paper evidence

- Conflict-type-only train+dev lookup: 1.0000 held-out test accuracy.
- Type-only lookup: 0.9667 accuracy / 0.9471 macro-F1.
- Reference policy: 0.8889 / 0.9145 on test.
- Structured LLM: 0.9000 / 0.9040 on test.
- The paired family-cluster interval for reference minus LLM includes zero.
- Reference policy: 0/33 observed action false commits with a one-sided 95% upper
  bound of 0.0868, alongside 10/45 missed updates.
- Full-corpus ablations only as mechanism diagnostics, clearly separated from
  held-out policy comparisons.

The 0.9222 full-corpus score may appear only in a secondary diagnostic context,
never as the headline method result.

## Excluded evidence

- The incomplete 174/180 six-shot prediction run.
- External-system action rankings produced through non-native mappings.
- Every existing LongMemEval number, including the contaminated v7 run and the
  selection-biased 77.2% failure replay.
- Claims of population safety, external validity, non-inferiority, calibrated
  confidence, long-lived deployment performance, or multi-human agreement.

The archived downstream and external-adapter analyses remain available for
provenance and failure analysis but are not inputs to the main manuscript.

## Route and submission gate

Target a venue that explicitly welcomes dataset analysis, evaluation,
reproducibility, or negative findings. Select the live venue and template only
after checking its current official call; do not encode a stale deadline in the
repository.

The current paper can be circulated as an honest audit draft. A stronger
capability paper requires the independently generated MGP-6 v3 confirmation set
defined in `benchmarks/mgp6/MGP6_V3_INDEPENDENT_PROTOCOL.md`. Before submission:

1. regenerate the 10,000-sample validity audit from released per-item files;
2. pass the bibliography audit and compile the anonymous PDF from a clean
   build directory;
3. keep the shortcut-failure result before all policy comparisons;
4. verify that every number in the abstract and tables traces to the audit JSON;
5. keep human and model-panel annotation evidence separate;
6. run a fresh related-work and venue-policy check against primary sources;
7. obtain redistribution consent for any raw human annotations.

If independent v3 data, three-human annotation, or a clean downstream run are
not completed, state that limitation; do not simulate or impute them.

## One-paper decision

Keep one paper. The single-session preference intervention and downstream
failure taxonomy do not yet have an independently executed experiment and do
not justify a separate contribution.
