# ASK Paper Final Audit

Date: 2026-08-06

## Final paper identity

The paper is about ASK, a storage-independent governance contract for durable
memory writes in language agents. ASK separates a controller proposal from a
validated state transition and from later retrieval and answer generation. Its
three public actions are KEEP, SUPERSEDE, and ABSTAIN, but the contribution is
the integrated decision, transition, lineage, audit, and layered-evaluation
contract rather than a three-class classifier. MGP-6 v4.3 is one controlled
diagnostic. LongMemEval-M V12 is one downstream runtime evaluation.
MGP-Natural is a quarantined natural-dialogue evidence track under construction.

## Authoritative sources

- Manuscript entry point: `paper/paper_1/main.tex`
- Manuscript sections: `paper/paper_1/sections/*.tex`
- Appendix and bibliography: `paper/paper_1/appendix.tex` and
  `paper/paper_1/references.bib`
- Generated tables and figures: `paper/paper_1/tables/` and
  `paper/paper_1/figures/`
- Reference protocol: `src/ask/protocol/`
- Evaluated runtime: `src/ask/pipeline/orchestrator.py` and
  `src/ask/memory/operations.py`
- Claim ledger: `claims/claims.json`, `claims/source_inventory.json`, and
  `claims/mismatch_report.json`
- Final machine-readable paper manifest:
  `reports/paper_final_metrics_manifest.json`
- Compiled output: `build/manuscripts/paper.pdf`

The archival Markdown exports, historical reports, external sibling archives,
and prose summaries are not authoritative when they disagree with raw
predictions, judgments, action logs, manifests, or regenerating scripts.

## Verified ASK components

### Reference protocol

The repository implements content-addressed evidence and configuration
identities, adapter-declared replay scope, typed records, KEEP/SUPERSEDE/ABSTAIN
transition semantics, retained predecessor lineage, active-state filtering,
transition events, and invariant checks. Protocol tests cover versioned,
multi-record, and temporal-event modes.

### Evaluated LongMemEval runtime

The V12 runtime extracts candidates, resolves a related active record, computes
the five logged features `(c,e,f,r,rho)`, applies a deterministic controller,
and performs SQLite mutations. SUPERSEDE retains the predecessor and links the
successor inside a transaction. Normal retrieval filters to active records, and
historical traversal follows lineage. The action log supports exact replay of
the scorecard decision.

The generic reference validator and generic `TransitionEvent` are not invoked
or emitted by this V12 SQLite mutation path. Source session and turn provenance
remain in pipeline traces rather than a fully normalized runtime provenance
table. The paper now states this boundary directly.

## Evaluated controllers

- MGP-6 v4.3 frozen composed controller: structured model action plus a
  public-indexed-evidence guard. Only one frozen configuration was scored on the
  sealed hidden split.
- MGP-6 development diagnostics: model-only and rule-only components,
  structural baselines, scorecard adapter, ablations, and semantically mapped
  external adapters. These are development evidence only.
- LongMemEval-M V12 controller: deterministic five-feature scorecard over
  extracted candidates. Exact log replay establishes execution fidelity, not
  gold action correctness.
- Historical MGP-6 v2 systems: retained only to document shortcut discovery and
  mechanism behavior.

## Evaluation datasets and versions

| Evidence stream | Version and denominator | Status | Defensible use |
|---|---:|---|---|
| MGP-6 | `4.3.0-human-validated-final`; 900 items, 100 components; hidden `n=540` | Primary controlled diagnostic | Write-action accuracy, error type, clustered uncertainty, cost analysis |
| ASK protocol tests | Current repository revision | Primary conformance | Transition and invariant semantics |
| LongMemEval-M | V12 fixed 180-question slice | Downstream final candidate | Answer outcome and runtime trace analysis; no per-candidate write gold |
| MGP-6 v2 | 180-item historical pilot | Diagnostic only | Shortcut and construct-failure evidence |
| External adapters | Public development mappings | Mapped diagnostic | Harness compatibility only, not native-system superiority |
| MGP-Natural v0.1.0 | 36-item Wikipedia discussion seed from 76 excerpt rows | Quarantined, not scored | Feasibility and failure discovery only |
| MGP-Natural v0.2.2 | StudyChat and WikiConv construction software plus aggregate private intake audit | Quarantined, not scored | Prospective human-AI and human-human workflow only |

## Primary and non-primary experiments

Primary evidence consists of the single frozen MGP-6 v4.3 hidden run, current
reference-protocol tests, and the V12 LongMemEval final-candidate comparison with
its disclosed manifest anomaly. MGP-6 development comparisons are supportive
and selected on public data. MGP-6 v2, external mappings, successor work,
incomplete runs, private MGP-Natural construction data, and post-hoc
counterfactual replays are explicitly non-primary.

## Corrected claims

- Reframed title, abstract, introduction, method, results, and conclusion around
  ASK rather than MGP-6.
- Distinguished controller decisions, state transitions, lineage, retrieval,
  and downstream answers.
- Distinguished the generic tested protocol from the narrower evaluated SQLite
  runtime.
- Changed MGP-6 v4.3 from a broadly released benchmark claim to a controlled
  diagnostic with no selected public redistribution license.
- Replaced item-level uncertainty with component-cluster intervals where the
  component is the defensible unit.
- Marked LongMemEval V12 as a final candidate because its historical manifest is
  nonterminal and the homogeneity report contains a stale launcher hash.
- Marked external-system action mappings as approximate diagnostics.
- Added MGP-Natural as an explicit prospective natural-dialogue track with
  separate human-human and human-AI annotation and continuity requirements.

## Removed claims

- MGP-6 as the paper's primary identity or a community benchmark release.
- Native superiority over external memory systems from mapped actions.
- End-to-end replay of the LongMemEval pipeline from the V12 action log.
- Runtime use of the generic ASK validator or generic transition-event schema.
- Generalization from LongMemEval dialogue to natural interaction.
- Any MGP-Natural score, independent gold status, valid held-out split,
  publication eligibility, or mixed-track headline.
- Priority, universal safety, certification, and population-generalization
  language.

## Unresolved evidence gaps

1. MGP-6 v4.3 has no selected public redistribution license.
2. The V12 run retains `status: running`, `exit_code: 1`, and a stale launcher
   hash in its homogeneity report despite complete adjudicated outputs.
3. LongMemEval provides no gold write action per extracted candidate and uses
   one answer model, one judge, one seed, and one 180-question slice.
4. The V12 runtime does not serialize the generic transition event and keeps
   source provenance in traces rather than normalized memory records.
5. MGP-Natural requires original-source integrity checks, rights and privacy
   approval, protocol freeze, independent annotation, adjudication, and
   continuity-aware track-specific splits before scoring.

## Build and readiness

The canonical PDF builds successfully as a 47-page authored manuscript. All
47 pages were rendered and inspected for clipping, overflow, figure order,
table readability, and unresolved references. The advisor and release checks
pass, including 686 main tests with 14 documented optional skips; the vendored
MGP-Natural v0.2.2 suite passes 132 tests. The final validation outcomes are
recorded in `reports/REPRODUCIBILITY_STATUS_FINAL.md`.

## Readiness verdict

**CONDITIONAL GO for the bounded manuscript.** The scientific story and
manuscript are complete within the stated evidence boundaries. The repository's
publication-readiness engine remains **NO_GO** with 15 external, human, legal,
venue, or scientific-evidence gates open. Public artifact release and an
unqualified reproducibility claim remain blocked by licensing, V12 provenance
anomalies, private-source restrictions, and the unfinished MGP-Natural human and
legal gates.
