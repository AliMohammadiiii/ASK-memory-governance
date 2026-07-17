# Scientific source of truth

Audit date: 2026-07-15. Machine-readable companions: `artifacts/analysis/mgp6_validity_audit.json`, `artifacts/results_ledger.json`, `artifacts/results_ledger.csv`, `artifacts/controller_run_comparison.json`, and `docs/audit/RUN_CLASSIFICATION.csv`.

The run-status vocabulary is `final_candidate`, `diagnostic_only`, `failure_replay_only`, `incomplete`, `invalid`, and `externally_pending`. Run status records provenance, but later validity evidence governs scientific eligibility. A numerical artifact does not become claim-eligible merely because it is complete, historically labelled `final_candidate`, or has a confidence interval.

## 1. MGP-6 v2

MGP-6 v2 is an author-designed synthetic diagnostic with 180 scenarios, six scenario types, and 60/30/90 train/development/test splits. It is not an established community benchmark, an independent test collection, or a representative population sample.

### Construct-validity decision (primary)

A lookup fitted on train+development and given only `conflict_type` reaches **1.0000 accuracy and 1.0000 macro-F1 on the held-out 90-item test split**; type alone reaches 0.9667 / 0.9471. The dataset therefore fails the shortcut-rejection gate: it cannot distinguish governance reasoning from recognition of author-visible scenario metadata. This finding supersedes the ledger's older `final_candidate` interpretation. Current v2 system scores are diagnostic observations on this generator.

The held-out lexical reference policy reaches 0.8889 / 0.9145 versus 0.9000 / 0.9040 for the structured LLM. The paired template-family cluster interval for reference minus LLM accuracy is [−0.0938, 0.0625]; this supports neither superiority nor non-inferiority. The authoritative computation is `scripts/analysis/audit_mgp6_validity.py` and its JSON/Markdown outputs.

### Historical complete-run results (diagnostic after the validity audit)

All values below were recomputed from complete 180-line prediction files and canonical reports:

| System | Action accuracy | Macro-F1 | Required disclosure |
|---|---:|---:|---|
| Rule KSA controller | 0.9222 | 0.9399 | Full-180 includes train and development; held-out test-90 is 0.8889 / 0.9145 |
| Qwen 3.5 9B LLM controller | 0.8889 | 0.8913 | Premise resistance is 0.0889, versus 1.0 for the rule controller |
| Zero-shot LLM decision baseline | 0.7000 | 0.6657 | Same author-designed diagnostic |
| B1 no memory | 0.3667 | 0.1789 | Deterministic reference baseline |
| B2 flat retrieval | 0.1333 | 0.0784 | Deterministic reference baseline |
| B3 recency | 0.4222 | 0.2203 | Deterministic reference baseline |
| B4 naive overwrite | 0.4222 | 0.2203 | Deterministic reference baseline |

The full-corpus reference-policy confusion is KEEP 24/24, ABSTAIN 66/66, and SUPERSEDE 76/90, with all 14 misses going to ABSTAIN. On held-out test it has 0/33 observed action false commits, but the one-sided 95% finite-sample upper bound is 0.0868; it also misses 10/45 required updates. Zero observed false commits is not a deployment-safety guarantee.

Complete ablations are within-generator mechanism diagnostics: no-abstain 0.5556 / 0.4278, no-provenance 0.7000 / 0.7428, no-typing 0.7889 / 0.5680, and no-lineage action accuracy 0.9222 with lineage integrity reduced from 0.8556 to 0.3689. They do not independently establish component necessity.

External adapter results for Letta, Mem0, and Graphiti are mapping-dependent diagnostics with both mappings disclosed. NOOP-to-ABSTAIN / NOOP-to-KEEP action accuracy is Letta 0.678 / 0.489, Mem0 0.622 / 0.400, and Graphiti 0.383 / 0.139. They are excluded from primary comparisons because the adapters do not expose equivalent native actions. MemOS is diagnostic_only at 0.144 because supersession is unobservable through its evaluated adapter.

### Annotation truth

Two annotation components must remain distinct:

1. One independent annotator covered the 90-item test split: raw agreement 0.9889 with 95% interval 0.9667 to 1.0, Cohen kappa 0.98146 with interval 0.93997 to 1.0, and one disagreement. This is diagnostic evidence about label consistency, but there is only one annotator and human identity rests on author attestation. It is not multi-annotator human agreement or independent construct validation.
2. Four LLMs covered the same 90 items: Fleiss kappa 0.9815 and majority vote matched author gold on all items. This is diagnostic_only model-audit evidence, never human inter-annotator agreement.

The 180-row human review sheet is 0/180 filled and invalid as evidence. Raw independent-human labels remain withheld from public release pending written redistribution consent.

### Restricted MGP-6 evidence

The six-shot decision run has 174 predictions for 180 gold items. A deterministic rescore aligns all IDs and treats the six missing predictions as INVALID, producing coverage-aware accuracy 0.7833 and macro-F1 0.7692. This artifact is incomplete and may be used only as a coverage-aware bound, not a completed-system result.

Smoke-family reports are invalid because selected files scored 1 to 10 predictions with a default 180-row denominator. The shipped over-forgetting and under-forgetting metrics saturate at 1.0 for all systems and are not claim-eligible.

## 2. LongMemEval-M

There is no final LongMemEval result.

### v7 diagnostic evidence

The v7 stratified 180-item run is diagnostic_only. It records controller 110/180 post-adjudication and 108/180 before adjudication; B4 114/180, B2 80/180, B3 43/180, and B1 9/180. The run contains 316 HTTP-402 traces, 388 empty extraction fallbacks, 736 extraction errors, at least 12 relaunches, and a no-op escalation tier because its big and fast models were identical. The same contaminated run has B4 above the controller, so it does not support controller superiority.

### Failure replay and the 77.2% construction

The no-thinking replay evaluated exactly the 70 v7 controller failures and judged 25/70 correct. It is failure_replay_only because fixes were designed from those failures, the same failures were replayed, contexts changed, and the judge changed.

The historical raw 135/180 = 75.0% and adjudicated 139/180 = 77.2% values are selection-biased constructions, not observed homogeneous runs. The adjudicated construction combines 110 retained v7 successes, 25 machine-judged replay repairs, and four Codex/GPT-5 semantic overrides. It is failure_replay_only. The four overrides are machine-assisted adjudication and must not be called independent human adjudication.

### Decisive top-up evidence

The Modal top-up is incomplete but non-empty. It completed 84 of the 110 former v7-success items: 71 remained correct and 13 regressed. Together with the 25/70 replay result, the observed v8 attempt is 96/154 raw.

For the 26 unresolved items, the full-180 raw accuracy bounds are:

- lower: 96/180 = 53.3%;
- upper: 122/180 = 67.8%.

If the four replay adjudication overrides are included, the bounds become 100/180 = 55.6% to 126/180 = 70.0%. Therefore this v8 attempt cannot reproduce 77.2%, even if every unresolved item is correct.

Single-session preference is equally clear. The replay repaired 0/19 prior failures. Of 11 former successes, 10 were top-upped and only 8 remained correct; one is unresolved. The observed attempt is 8/29 and can reach at most 9/30 = 30.0%. The 11/30 row in the failure-replay construction is a carry-forward artifact, not an unchanged v8 measurement.

### Frozen final run

The final-1.1 protocol specifies a homogeneous 180-item, five-system run with Qwen 3.5 9B as answerer and Gemma 4 31B as judge under an explicit free-to-paid fallback policy. An API smoke attempt failed before inference because the supplied credential returned HTTP 403 on minimal and provider-specific requests. No final predictions exist. The run is externally_pending, and the credential must not be reused or recorded.

## 3. Provenance chains

| Claim or diagnostic | Evidence chain |
|---|---|
| MGP-6 rule controller 0.9222 / 0.9399 | artifacts/mgp6_v2/ref_5systems/controller/report.json and predictions.jsonl → metrics_mgp6.py → benchmarks/mgp6/data/mgp6_v2.jsonl |
| MGP-6 six-shot coverage-aware bound | artifacts/results/mgp6_few6_report.json → 174 source predictions aligned to 180 gold IDs with six INVALID entries |
| v7 controller 110/180 | external://Master/ksa_controller/runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v7/controller/report.json; pre-adjudication original records 108/180 |
| replay 25/70 | external://Master/ksa_controller/runs/lme_m last version/lme_m_modal_qwen35_9b_v8_failures_nothink/controller/report.json |
| top-up 71/84 with 13 regressions | external://Master/ksa_controller/runs/lme_m last version/lme_m_modal_qwen_gemma_minilm_strat30_seed0_v8_topup110/controller/_shards/ |
| historical 139/180 construction | external://Master/ksa_controller/runs/lme_m last version/lme_m_v8_failure_replay_adjudicated/controller/report.json → selection-biased merge of v7 retained successes, replay failures, and four overrides |

The historical adjudicated manifest points to a replay directory name that does not exist. The actual completed replay pointer is the one shown above and in artifacts/controller_run_comparison.json. The evidence artifact is preserved; the public audit records the corrected mapping.

## 4. Source precedence and claim rules

1. Raw predictions and judgments outrank derived reports.
2. `artifacts/analysis/mgp6_validity_audit.json` governs MGP-6 validity interpretation.
3. `artifacts/results_ledger.json` is the canonical historical quantitative ledger.
4. `artifacts/controller_run_comparison.json` is the canonical LongMemEval run reconstruction.
5. `RUN_CLASSIFICATION.csv` and this document govern run status, subject to later documented validity audits.
6. Narrative reports, thesis text, proposals, and slides are secondary and must be corrected if they disagree.

No current MGP-6 v2 policy, ablation, or mapped-adapter row is eligible as a primary capability result because the shortcut gate failed. They may appear only as clearly labelled diagnostics, led by the shortcut probe and held-out null/trade-off analysis. The 77.2% LongMemEval value may be named only to explain why it was rejected; it is not a KSA performance result. Stronger claims require the independent v3 protocol and the externally pending homogeneous LongMemEval run to pass their respective gates.
