# Two-Page Thesis Summary

## Problem and contribution

Persistent memory turns an agent utterance into a durable side effect. A new
statement may be compatible with memory, may supersede a stale record, or may be
too ambiguous to commit. This thesis represents that boundary with three
explicit actions—KEEP, SUPERSEDE, ABSTAIN—over typed, provenance-tracked records
with supersession lineage. It evaluates the write action, resulting state, and
later answer separately.

The defensible contribution is an evaluation decomposition and validity audit,
not a claim that the update operations or the evaluated controller are new or
superior.

## Pilot and validity result

MGP-6 v2 is an author-designed 180-item pilot split 60/30/90 across
train/development/test. It contains 96 template families and 24 minimal-pair
groups. One independent human re-annotated the test split; a separate four-model
panel supplied an audit. This is not multi-human inter-annotator agreement.

The primary result is a failed shortcut gate. A conflict-type-only lookup fitted
on train+development reaches 1.000 test accuracy and macro-F1 without reading
the dialogue or memory state. A coarser type-only lookup reaches 0.9667 accuracy
and 0.9471 macro-F1. Thus family-disjoint item splitting does not isolate
evidence reasoning from scenario recognition.

## Policy diagnostics

On the 90-item test, the lexical reference policy reaches 0.8889 accuracy /
0.9145 macro-F1; the structured LLM policy reaches 0.9000 / 0.9040. Reference
minus LLM accuracy is −0.0111 and the paired template-family interval
[−0.0938, 0.0625] includes zero. The data support neither superiority nor
non-inferiority.

The reference makes 0/33 observed action false commits, but the one-sided 95%
upper bound is 0.0868; it misses 10/45 required updates. The structured LLM
makes 2/33 false commits and misses 7/45 updates. Commit-averse expected loss
favours the reference (0.111 vs 0.189), while update-responsive loss favours the
LLM (0.433 vs 0.556 for LLM vs reference). Confidence diagnostics are
descriptive because no independent calibration set exists.

Full-corpus ablations are retained only as within-generator mechanism checks.
The clearest measurement result is that removing lineage leaves action accuracy
at 0.9222 while lineage integrity falls from 0.8556 to 0.3689: action accuracy
alone can hide state-history corruption.

## Exclusions and next gate

The six-shot run is incomplete at 174/180 predictions. External-system action
rankings depend on non-native mappings. Existing LongMemEval runs are
contaminated, incomplete, or selection-biased. All are excluded from primary
capability claims.

The successor protocol requires controller/code freeze before data access,
independent scenario writers, all three actions inside every conflict family,
5/10/20-turn trajectories, a sealed test set, three blinded human annotators,
native external-system metrics, and family-clustered analysis. Until it is
executed, MGP-6 v2 remains a useful pilot and a cautionary example of how a
strong held-out score can coexist with severe construct leakage.
