# Contribution audit

Updated 2026-07-27. This ledger maps the repository's implemented and
experimental contributions to their location in the manuscript. It complements
`claims_evidence_matrix.md`, which records the evidential strength of numerical
claims.

## Contributions represented in the paper

| Contribution | Repository evidence | Manuscript position |
|---|---|---|
| A three-action write-governance formulation that separates state-preserving retention, lineage-preserving replacement, and refusal to commit | `src/ask/controller/`, `src/ask/memory/operations.py` | Sections 1, 3, and 5 |
| A typed five-dimensional write scorecard over extraction confidence, evidence quality, marker burden, signed relation, and stability prior, with type-conditional thresholds and a discrete relation guard | `src/ask/controller/features.py`, `score.py`, and `policy.py` | Abstract; Sections 1, 5.1, 8.3, 9, and 10 |
| An exact action-log replay and counterfactual mechanism audit that measures the action dependence of every dimension, the relation guard, and the type channels | `scripts/analysis/analyze_lme_scorecard.py`; `artifacts/analysis/lme_v12_scorecard_analysis.json` | Sections 8.3 and 9; Appendix |
| An append-only memory state machine with retained predecessors, explicit successor links, active-state invariants, and active-only versus historical retrieval | `src/ask/memory/operations.py`, `src/ask/memory/models.py`, `src/ask/audit/action_log.py` | Sections 3 and 5; Appendix |
| A layered evaluation harness that scores the write action, state invariants, lineage, superseded-record recoverability, stale retrieval, selective risk, and asymmetric operational costs separately | `src/ask/eval/`; MGP-6 evaluator artifacts | Sections 3, 4, 6, and 7; Appendix |
| MGP-6 v4.3, a component-controlled diagnostic with all three actions inside each semantic component, component-isolated splitting, duplicate and shortcut gates, a frozen hidden set, and release manifests | `benchmarks/mgp6/mgp6_v4_3/`; release and integration reports | Sections 4, 6, 7, and 9 |
| A composed controller whose model and public-evidence rule proposals are both logged, enabling a repair-versus-regression decomposition of the conservative guard | v4.3 response `guard_trace` fields; benchmark-analysis artifact | Sections 4, 7, and 9 |
| A homogeneous LongMemEval pipeline that exposes extraction, relation classification, governed state construction, retrieval, answer generation, and judgment as separately auditable stages | `src/ask/pipeline/orchestrator.py`; V12 run artifacts | Sections 6 and 8 |
| Stage-level call, prompt-token, completion-token, and latency accounting showing where memory-governance computation is spent | V12 extraction/relation traces; MGP-6 response telemetry | Sections 7 and 8 |
| An auditable deterministic date, numeric, and list computation aid whose proposals and answer-level overrides remain separate from memory writes | `src/ask/controller/computation.py`; V12 answer extras | Sections 8 and 9 |
| Validity-first negative results: v2 structural leakage, per-family dependence, contaminated-run exclusion, non-equivalent carry-forward exclusion, and mapping-aware external-system comparisons | validity audits; evidence registry; controller-run audit reports | Sections 4, 7, 9, and 10 |
| Reproducibility infrastructure: structured action logs, content-addressed caches, resumable stages, deterministic replays, configuration snapshots, and claim/evidence ledgers | `src/ask/audit/`, pipeline artifacts, release scripts, this ledger | Sections 5, 6, and 9; Appendix |

## Novelty boundary

The paper does not claim that KEEP/UPDATE/ABSTAIN, typed memory, provenance,
lineage, selective prediction, or operation-level memory evaluation is novel in
isolation. The defensible novelty is their executable conjunction:

1. the write transition is the primary evaluation object;
2. action, state, lineage, retrieval, and downstream answer consequences remain
   separately observable;
3. the deployed write rule is inspectable and exactly replayable from logged
   features;
4. its effective decision mechanism is measured by dimension, memory type, and
   guard rather than inferred from weights alone; and
5. a controlled semantic diagnostic and a downstream long-memory benchmark are
   used together, with explicit boundaries on what each can establish.

The closest feature-based precedent governs retrieval or injection, whereas
this scorecard governs write-time state transition. Recent memory-update work
does include operation labels, conflict handling, and update evaluation, so the
paper positions ASK as a governance-and-measurement architecture rather than
claiming priority over those ingredients.

## Claims intentionally excluded

- No claim that the five weights or type thresholds are learned, calibrated, or
  optimal.
- No claim that exact V12 replay establishes per-write correctness; there are no
  candidate-level gold write labels in that run.
- No hidden-set comparison for v4.3 baselines, ablations, external systems, or
  successor configurations.
- No claim that v2 demonstrates general evidence reasoning.
- No claim that one LongMemEval slice, answer model, or judge establishes broad
  deployment generality.
- No claim that KEEP has identical storage semantics in the single-slot
  diagnostic and multi-record runtime; in both settings it means no
  invalidation of the compared prior.
