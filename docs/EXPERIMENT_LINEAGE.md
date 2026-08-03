# Experiment lineage

## Controlled diagnostic lineage

```text
MGP-6 v2
  -> shortcut audit: conflict type predicts action
  -> construct-failure lesson only
  -> MGP-6 v4.3 matched semantic components
      -> component-disjoint train/dev/hidden split
      -> development controller and guard selection
      -> one frozen ASK-MGP hidden execution
      -> consumed hidden predictions
      -> private deterministic scoring
      -> paper controlled-diagnostic claims
```

The v4.3 hidden split is consumed. It cannot be reopened for controller
selection, new baseline comparison, or independent confirmation.

## Downstream lineage

```text
LongMemEval v7
  -> provider and extraction contamination
  -> diagnostic only
  -> selection-biased v8 failure replay and partial top-up
  -> rejected as final evidence
  -> homogeneous V12 slice and frozen answer/judge policy
      -> resumed sharded controller execution
      -> preserved ASK-LME action log
      -> controller and naive-overwrite judgments
      -> paired downstream analysis
      -> exact final-policy replay from stored feature snapshots
      -> paper downstream and mechanism claims
```

V12 is the current downstream evidence source but is not a clean end-to-end
reproduction. The original manifest remains historical evidence. A derived
manifest may document verified hashes and anomalies but cannot erase the stale
launcher hash, resume history, failed launcher exit, or post-resume finalization
problem.

## Adapter lineage

- ASK-MGP preserves model proposal, indexed-evidence rule proposal, verdict,
  evidence digest, guard identifier, final action, and transition inputs. Its
  replay scope is composition plus deterministic transition. It does not replay
  the stochastic model call.
- ASK-LME preserves feature snapshots, scores, thresholds, relation guard,
  ordered rules, identifiers, final action, and transition inputs. Its replay
  scope is exact final policy plus deterministic transition where state inputs
  exist. Extraction and relation model outputs are preserved inputs.
- Both adapters implement the ASK audit contract but are not the same predictor
  and do not share storage cardinality.
