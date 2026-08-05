# Adapter contract

An ASK adapter declares `adapter_id`, version, storage mode, and replay scope;
records immutable configuration and evidence identities; emits a typed
`DecisionTrace`; and implements deterministic replay for its declared scope.

- **ASK-MGP** records the model proposal, rule proposal, rule verdict, guard
  rule, evidence, and whether the guard overrode model abstention. The frozen
  composition changes only model Abstain to a non-Abstain rule proposal; model
  Keep and Supersede are not overridden. Its claim is composition-and-transition
  replay, not full model-inference replay.
- **ASK-LME** records the feature schema and values, memory type, raw scores,
  thresholds, ordered rules, relation guard, prior/candidate IDs,
  configuration, and evidence. Its deterministic scorecard and transition are
  replayable; upstream extraction or external judge calls are not thereby
  reproduced.

Adapters must never read hidden labels during prediction, silently change the
frozen policy, omit fallbacks, or claim broader replay than their logged fields
support.
