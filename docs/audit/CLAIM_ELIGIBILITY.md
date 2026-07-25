# Claim eligibility

Audit date: 2026-07-15. The canonical run-status vocabulary is limited to `final_candidate`, `diagnostic_only`, `failure_replay_only`, `incomplete`, `invalid`, and `externally_pending`. `RUN_CLASSIFICATION.csv` assigns historical run status; later construct-validity evidence can further restrict claim eligibility. For MGP-6 v2, `artifacts/analysis/mgp6_validity_audit.json` supersedes the older `final_candidate` interpretation.

## Status policy

| Status | Permitted use | Prohibited use |
|---|---|---|
| final_candidate | Candidate for review only after all later validity gates pass | Treating the label itself as permission for a headline or capability claim |
| diagnostic_only | Failure analysis, implementation lessons, and clearly labeled historical context | Headline comparison, superiority claim, abstract performance claim, or pooled meta-analysis with final rows |
| failure_replay_only | Methodological post-mortem of failure-targeted replay; historical value may be named only to explain invalidation | Performance estimate, improvement claim, confidence interval presented as generalization evidence, or camera-ready result |
| incomplete | Coverage and best/worst-case bounds with explicit observed and target denominators | Point estimate represented as a completed run or direct ranking against completed systems |
| invalid | Evidence-preservation and failure-ledger discussion only | Any scientific result or aggregate |
| externally_pending | Protocol, model, dataset, and blocker disclosure | Any accuracy, comparative result, or statement that the experiment completed |

## Audience eligibility

The status assignment applies to each material row in RUN_CLASSIFICATION.csv:

| Status | Paper main results | Thesis main results | CV | Proposal | Diagnostic discussion |
|---|---|---|---|---|---|
| final_candidate | Only if no later validity gate supersedes it | Only if no later validity gate supersedes it | Only after independent validation | Only as explicitly preliminary evidence | Yes |
| diagnostic_only | No | Only in a clearly labeled limitations or failure-analysis section | No quantitative performance claim | May motivate open work without presenting the value as validated performance | Yes |
| failure_replay_only | No | Only as a research-integrity post-mortem | No | No performance claim; at most explain why confirmation is planned | Yes, with selection-bias disclosure |
| incomplete | No | Bounds only, with observed and target denominators | No | May state experiment is incomplete without a headline value | Bounds and execution analysis only |
| invalid | No | Evidence ledger only | No | No | Failure history only |
| externally_pending | No | Protocol and blocker only | No result | May state planned evaluation and blocker, never an outcome | Protocol discussion only |

No LongMemEval value in the current ledger is eligible for a CV or proposal performance claim. The historical 77.2% value must be removed from both.

## Allowed MGP-6 v2 diagnostic claims

The shortcut audit makes all current v2 policy results diagnostic. The following statements are allowed only in a diagnostic/validity analysis, not as headline capability claims:

- Conflict type alone reaches 1.0000 accuracy and macro-F1 on the held-out 90-item test split; type alone reaches 0.9667 / 0.9471. This failed shortcut gate is the primary v2 result.
- The lexical reference policy reaches 0.8889 / 0.9145 on test versus 0.9000 / 0.9040 for the structured LLM. The paired template-family interval for the accuracy difference is [−0.0938, 0.0625], supporting neither superiority nor non-inferiority.
- The reference policy records 0/33 observed action false commits on test, with a one-sided 95% upper bound of 0.0868, and misses 10/45 required updates. Cost matrices can reverse the preferred policy.
- Full-corpus policy, baseline, and ablation values may be shown only as secondary mechanism diagnostics; the corpus includes training and development items.
- Letta, Mem0, Graphiti, and MemOS adapter values are mapping/harness-specific and excluded from primary comparison; native-operation evaluation is still required.
- Agreement with one independent annotator may be reported as raw agreement 0.9889 and Cohen kappa 0.98146 over 90 test items only if it is called a one-human label audit, not multi-human IAA or construct validation.

Every MGP-6 statement must say that the dataset is author-designed, synthetic, shortcut-leaking, and diagnostic rather than an established community benchmark. A full-180 score must not be called a test score.

## Restricted MGP-6 claims

- The six-shot result is incomplete. The only eligible statement is: 174 predictions were aligned to 180 gold IDs, six missing IDs were scored INVALID, and the resulting coverage-aware bound is 0.7833 accuracy and 0.7692 macro-F1. It must not enter the completed-system ranking.
- MemOS is diagnostic_only because the adapter cannot expose supersession. Its 0.144 result is a harness bound, not a capability estimate.
- The four-LLM panel is diagnostic_only and may be described as a model audit. It must never be described as human inter-annotator agreement.
- The unfilled 180-row human review sheet and all smoke-family reports are invalid.
- Over-forgetting and under-forgetting values are not claim-eligible because they saturate at 1.0 for every evaluated system.

## LongMemEval claim decision

There is no final LongMemEval result.

### Allowed diagnostic statements

- The contaminated v7 run recorded controller 110/180 post-adjudication and naive overwrite 114/180; both are diagnostic_only because the run contains provider and extraction failures.
- A failure-targeted replay repaired 25 of 70 prior controller failures, including 0 of 19 single-session-preference failures. This is failure_replay_only.
- The incomplete Modal top-up observed 71 correct and 13 regressions among 84 completed former-success items.
- Combining those 84 top-up observations with the 70-item replay yields 96/154 raw observed. The full-180 raw bounds are 53.3% to 67.8%; adding the four replay adjudication overrides gives bounds of 55.6% to 70.0%.
- For single-session preference, the observed attempt is 8/29 and can reach at most 9/30 because the replay repaired 0/19 and only 8/10 completed former successes remained correct.

### Prohibited LongMemEval claims

- The historical 139/180 = 77.2% value must not be presented as ASK accuracy, a v8 result, an improvement over v7, or evidence of superiority. It is a selection-biased failure-replay construction and is classified failure_replay_only.
- The raw 135/180 = 75.0% construction is subject to the same prohibition.
- The 11/30 single-session-preference row in that construction must not be described as unchanged v7-to-v8 performance. The top-up shows regressions and caps this attempt at 9/30.
- The published-style confidence interval attached to 139/180 does not repair selection bias and must not be used as evidence of generalization.
- No claim may say the answer model alone caused replay persistence or repair because replay contexts and judging changed.

### Pending confirmation

The final-1.1 homogeneous five-system run is externally_pending. The supplied credential returned HTTP 403 before inference, so no result exists. It becomes eligible for review only after all of the following hold:

1. all five systems cover the same frozen 180 IDs;
2. answerer, provider policy, prompt bundle, embedder, retry policy, and judge policy match the frozen manifest;
3. actual judge provenance and fallback use are recorded per item;
4. no empty-response or deterministic scoring fallback is silently counted as model output;
5. the homogeneity verifier and aggregate recomputation pass; and
6. raw predictions and judgments are retained privately while only privacy-reviewed aggregates are packaged publicly.

Passing those gates makes the new run reviewable; it does not retroactively validate the 77.2% construction.

## Safe manuscript wording

Recommended MGP-6 wording:

> MGP-6 v2 is an author-designed diagnostic that fails its shortcut gate: conflict type alone reaches 100% held-out accuracy. On the test split, the lexical reference policy reaches 88.9% versus 90.0% for the structured LLM, with a template-family interval spanning zero. These are mechanism diagnostics, not estimates of general memory-governance capability.

Recommended LongMemEval wording:

> LongMemEval evidence remains diagnostic. A prior 77.2% figure was a selection-biased failure-replay construction; an incomplete top-up observed 13 regressions among 84 retested former successes and bounded that attempt below 77.2%. A frozen homogeneous rerun is externally_pending.

## Source precedence

For quantitative claims, use this order:

1. raw prediction and judgment artifacts;
2. `artifacts/analysis/mgp6_validity_audit.json` for MGP-6 validity interpretation;
3. `artifacts/results_ledger.json` and `artifacts/controller_run_comparison.json` for historical quantitative provenance;
4. `RUN_CLASSIFICATION.csv` and `SCIENTIFIC_SOURCE_OF_TRUTH.md`;
5. generated reports;
6. narrative reports, proposals, thesis prose, and slide text.

If two layers disagree, the higher layer in this list wins and the lower artifact must be corrected before release.

## Metadata-completeness rule

Historical artifacts do not consistently record embedding model, prompt/config hashes, seed, and code revision in one run manifest. Missing metadata is not inferred from nearby filenames or later configuration. RUN_CLASSIFICATION.csv and ARTIFACT_TRUTH_TABLE.csv record the available model/judge/scope facts; INPUT_INVENTORY.md binds source directories and datasets; artifacts/manifests/freeze_hashes.json binds the pending final-1.1 code, prompt bundle, configuration, seed-0 slice, and MiniLM embedder policy. Historical LongMemEval rows remain below final_candidate in part because they cannot pass that complete provenance gate.
