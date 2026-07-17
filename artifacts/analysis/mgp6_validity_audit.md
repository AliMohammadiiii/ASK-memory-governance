# MGP-6 v2 construct-validity audit

> This is a diagnostic audit of an author-designed collection, not independent validation.

## Shortcut results

| Baseline fitted on train+dev | Held-out test accuracy | Macro-F1 |
| --- | ---: | ---: |
| Type-only lookup | 0.9667 | 0.9471 |
| Conflict-type-only lookup | 1.0000 | 1.0000 |

A perfect or near-perfect shortcut result is evidence of construct leakage, not model quality. It means the current collection cannot isolate evidence reasoning from scenario-family recognition.

## Test-set system diagnostics

| System | Accuracy | Family-cluster 95% CI | False commit | Missed update | Unnecessary abstention | ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| rule | 0.8889 | [0.8125, 0.9688] | 0.0000 | 0.2222 | 0.1754 | 0.1561 |
| llm_structured | 0.9000 | [0.8438, 0.9583] | 0.0606 | 0.1556 | 0.1228 | 0.3017 |
| llm_zero_shot | 0.6778 | [0.5625, 0.7917] | 0.5758 | 0.2222 | 0.1754 | 0.1778 |

## Claim boundary

- Type-only and metadata-only results quantify label leakage; they are not competitive memory systems.
- Cluster bootstrap addresses within-collection dependence but cannot establish external validity.
- No non-inferiority or equivalence claim is licensed because no margin was pre-specified.
- Zero observed action false commits receive a finite-sample upper bound, never a zero-risk interpretation.

The independent, balanced, multi-action-per-family successor set remains required before any external-generalization or population-safety claim.
