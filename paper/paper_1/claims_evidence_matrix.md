# Claims → evidence matrix

Updated for the diagnostic-paper rewrite on 2026-07-15. The machine-readable
source for test metrics is `artifacts/analysis/mgp6_validity_audit.json`.

| # | Claim | Location | Status | Evidence |
| --- | --- | --- | --- | --- |
| P1 | MGP-6 v2 is a 180-item author-designed pilot with a 90-item held-out test, 96 template families, and 24 minimal-pair groups. | §4 | verified descriptive | gold JSONL + validity audit |
| P2 | Conflict type deterministically maps to the action; a train+dev conflict-type lookup reaches 1.000 test accuracy. | abstract, §4, §7.1 | verified; invalidates construct-isolation claim | validity audit `shortcut_audit.conflict_type` |
| P3 | A type-only train+dev lookup reaches 0.9667 accuracy / 0.9471 macro-F1 on test. | abstract, §7.1 | verified shortcut | validity audit `shortcut_audit.type` |
| P4 | The reference policy reaches 0.8889 / 0.9145 on test; the structured LLM reaches 0.9000 / 0.9040. | abstract, §7.2, Table 2 | verified on pilot; diagnostic only | released per-item predictions + audit |
| P5 | Reference minus structured-LLM accuracy is -0.0111 and its paired template-family interval includes zero. | §7.2 | verified null; no superiority/non-inferiority claim | paired cluster bootstrap |
| P6 | The reference has 0/33 observed action false commits, with one-sided 95% upper bound 0.0868, and misses 10/45 updates. | abstract, §7.3, Table 2 | verified finite-sample diagnostic | validity audit test metrics |
| P7 | Commit-averse and update-responsive cost matrices reverse the preferred system. | §7.3 | verified sensitivity analysis | frozen cost matrices + audit |
| P8 | Full-corpus ablations show action/state metrics can diverge; no-lineage preserves 0.9222 action accuracy while lineage integrity falls 0.8556→0.3689. | §7.4 | verified within-generator mechanism check | ablation prediction reports |
| P9 | The six-shot run is incomplete; mapped external-system scores and existing downstream runs are excluded from main comparisons. | §6, §7.4, §9 | verified exclusion | artifact ledger and run audit |
| P10 | Independent construction, three-human annotation, long trajectories, native external metrics, and a hidden confirmation test remain future requirements. | §9, appendix | prospective, not executed | `benchmarks/mgp6/MGP6_V3_INDEPENDENT_PROTOCOL.md` |

## Guardrails

- The 0.9222 full-corpus score is not a headline generalization result.
- No policy-superiority, non-inferiority, population-safety, calibrated-confidence,
  long-lived-deployment, or LongMemEval-improvement claim is made.
- One human annotator plus a model panel is never described as multi-human IAA.
- The lexical reference policy is not described as the unused five-feature
  scorecard implementation.
- Missing independent data, human labels, hosted runs, and clean downstream
  evidence are not imputed.
