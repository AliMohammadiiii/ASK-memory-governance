#!/usr/bin/env python3
"""Builds CLAIM_CHECK_REPORT.csv and CLAIM_CHECK_SUMMARY.md (aggregate-only; no benchmark text)."""
import collections, csv, os

OUT = os.path.dirname(os.path.abspath(__file__))
S, W, C, U = 'SUPPORTED', 'WEAKER_THAN_STATED', 'CONTRADICTED', 'UNVERIFIABLE'
HID = 'artifacts/analysis/mgp6_v43_full_benchmark_analysis.json (hidden_v43)'
RJ = 'review_claimcheck/claimcheck_recomputed.json'
R = []


def add(file, loc, excerpt, cat, verdict, ev, note, fix=''):
    R.append(dict(file=file, loc=loc, excerpt=excerpt, cat=cat, verdict=verdict, ev=ev, note=note, fix=fix))


AB, IN, IF, MG, LM, DI, CO, AP, RW = ('sections/00_abstract.tex', 'sections/01_introduction.tex', 'sections/03_interface.tex',
                                      'sections/04_mgp6.tex', 'sections/05_lme.tex', 'sections/06_discussion.tex',
                                      'sections/07_conclusion.tex', 'sections/08_appendix.tex', 'sections/02_related_work.tex')

# ------------------------------------------------------------------ abstract
add(AB, 'line 2, sentence 3', 'The reference specification was written after the evaluations reported here, no evaluated system calls it', 'FACT', S,
    'git log of src/ask/protocol (first commit 2452e97, 2026-08-03); manifest/action-log dates 2026-07-18 to 07-19; hidden run 2026-07-26; grep of imports (tests only); phase5_callpath',
    'Only tests/test_ask_protocol.py and tests/test_ask_formal_properties.py import ask.protocol.')
add(AB, 'line 2, sentence 3', 'its validator accepts several classes of non-conforming state', 'FACT', S,
    'phase6_validator/VALIDATOR_PROBE_TABLE.csv: 19 rows S01-S12, K01-K05, I01-I02 all ACCEPTED',
    'Classes: retained-predecessor rewrite, unrelated-record deletion or mutation, extra record, wrong event ids, digest mismatches.')
add(AB, 'line 2, sentence 5', '0.848 action accuracy (macro-F1 0.848) on 540 hidden items drawn from 60 components', 'NUMBER', S,
    HID + ': accuracy 0.84815 (458/540), macro_f1 0.84787; configs/experiments/mgp6_v43/FROZEN_CONFIG_INDEX.json split_component_counts hidden 60',
    'Both values round to 0.848.')
add(AB, 'line 2, sentence 5', 'one configuration frozen before hidden scoring', 'FACT', S,
    'FINAL_HIDDEN_CONFIG.json created_at_utc 2026-07-26T05:29:42Z; FINAL_HIDDEN_EXPERIMENT_REPORT.md prediction SHA-256 e6a598... sealed before private scoring; prompt hashes recomputed from the repo prompt file (system_prompt_hash f802dc83..., prompt_hash 3ffa2ae8... both match)',
    'Record-based; the hidden inputs themselves are private and were not inspected.')
add(AB, 'line 2, sentence 5', 'three actions differ only in which two of six pooled sentences the dialogue indexes', 'FACT', W,
    'Recomputed on public dev and train with src/ask/eval/mgp6_v43.py: in 0 of 60 dev (component, length) triples is the numbering of the six sentences identical across the three items; 118 of 180 item pairs move all six sentences',
    'The pool and the partition of indexed pairs hold, but the numbered order of the six sentences is also permuted between the three actions. "Only" is not supported as stated; the order change is balanced (mean indexed position 3.575 for each action) but is an additional difference.',
    'Say the actions differ in the indexed pair and in the numbering of the pooled sentences, or drop "only".')
add(AB, 'line 2, sentence 6', 'MGP-6 v2 is retained as a failed construct-validity check', 'FACT', S,
    'artifacts/analysis/mgp6_validity_audit.json shortcut_audit.conflict_type.train_dev_lookup test_accuracy 1.0', '')
add(AB, 'line 2, sentence 7', 'recorded 128 correct answers before and 137 after nine manual judge adjudications', 'NUMBER', S,
    RJ + ' lme: correct_raw 128, correct_final 137, adjudicated 9 (all False to True)',
    'See separate row on the wording "judge adjudications" (one of the nine overrode a deterministic pre-judge guard).')
add(AB, 'line 2, sentence 7', 'decision log of 12,654 rows is recomputed exactly from the logged features', 'NUMBER', S,
    RJ + ' action_log: n 12654, independent re-implementation of the scorecard gives 0 action mismatches, max abs deviation 0.0; phase15 V12_REPLAY_R1.json',
    'Recomputation also uses the logged thresholds and the default scorecard weights.')
add(AB, 'line 2, sentence 9', 'associates most of the development gain with the decision prompt rather than with evidence routing', 'ROLE_MIXING', W,
    'phase13 routing_check_analysis.json and recomputation: substitute-model total gain (routed live minus full-payload zero-shot) is +0.131; the manuscript model gain in Table 2 is 0.844 minus 0.339 = +0.505',
    '"The development gain" reads as the qwen gain in Table 2. The decomposition accounts for a +0.131 gain on a different model that starts at 0.76. The qwen gain is not decomposed.',
    'Write "most of the +0.13 gain observed with the substitute model", and state that the qwen gain was not decomposed.')
add(AB, 'line 2, sentence 10', 'Each element of ASK has prior or concurrent precedent, and we make no priority claim.', 'NOVELTY', S,
    'phase9_saturation/SATURATION_STATEMENT.md; phase8 PHASE8_FUNCTIONAL_EQUIVALENCE.md 8.5(1)', 'Bounded statement; consistent with the audit record.')

# ------------------------------------------------------------------ introduction
add(IN, 'line 3', 'Most evaluations of long-term memory report the accuracy of final answers', 'FACT', U,
    'No citation in the sentence; no survey in the evidence files', 'Generalization over the literature without support.',
    'Cite the benchmarks surveyed or soften to "Several".')
add(IN, 'line 3', 'replacing a value on weak evidence destroys information, and refusing a well-supported update leaves the memory stale', 'CAUSAL', U,
    'No evidence file; ASK SUPERSEDE retains the predecessor (memory/operations.py supersede)',
    'Stated as fact about failure costs. It does not hold for ASK SUPERSEDE, which retains the predecessor, so the sentence applies only to replace-in-place memories.',
    'Qualify as "for memories that overwrite in place" and add a citation or mark as motivation.')
add(IN, 'line 5', 'SUPERSEDE replaces a stored item with a successor while retaining the predecessor and a link to it', 'FACT', S,
    'Released src/ask/memory/operations.py supersede (successor insert, UPDATE prior status, memory_relations row); V12 action log: 397 of 397 SUPERSEDE rows carry prior and resulting ids',
    'Evaluated-version memory module is not among the 17 hashed files; released code and log agree.')
add(IN, 'line 5', 'record that carries the candidate, the identifiers of the prior and resulting items, the features and thresholds, and a rationale', 'FACT', S,
    'controller/action_log.jsonl keys: candidate_text, candidate_type, prior_memory_id, resulting_memory_id, feature_c/e/f/r/rho, s_rev, s_abs, theta_sup, theta_abs, rationale', '')
add(IN, 'item 1, line 9', 'committed after both evaluations below, is imported only by tests, and its validator accepts all 19 of our self-consistent tampering probes', 'NUMBER', S,
    'git log; import grep; VALIDATOR_PROBE_TABLE.csv (19 accepted)', '')
add(IN, 'item 2, line 10', 'One configuration frozen before hidden scoring reached 0.848 action accuracy on 540 hidden items.', 'NUMBER', S, HID, '')
add(IN, 'item 2, line 10', 'holds the surface form of the evidence fixed within a component and varies only which sentences the dialogue indexes', 'FACT', W,
    'Same recomputation as the abstract row: pool identical across the three lengths (20 of 20 dev components), but numbering of the pooled sentences differs between actions',
    'Third location of the "only" statement; the sentence texts are fixed, the sentence order is not.', 'Same fix as the abstract row.')
add(IN, 'item 3, line 11', '128 correct before and 137 correct after nine manual adjudications of the judge\'s output', 'FACT', W,
    RJ + ' lme: adjudicated_with_judge_called 8 of 9',
    'Eight of the nine overrides changed a model-judge verdict. One changed a verdict from a deterministic pre-judge guard (judge_was_called false).',
    'Write "nine manual adjudications of the grader output" or state 8 judge verdicts and 1 guard verdict.')
add(IN, 'item 3, line 11', 'The run is exploratory by the terms of its own frozen analysis plan', 'FACT', S,
    'recovered_evaluated_code/FINAL_ANALYSIS_PLAN.md lines 1-6 (sha256 equals manifest 690b54b2...)',
    'FINAL_RUN_MATRIX.yaml labels the same run "classification: posthoc_confirmatory"; the two frozen files disagree in label.',
    'Optionally note the run-matrix label to pre-empt the discrepancy.')
add(IN, 'item 4, line 12', 'The log of 12,654 decisions permits exact recomputation of every logged action and score (replay level R1)', 'NUMBER', S,
    RJ + ' action_log r1_mismatches 0', '')
add(IN, 'Table 1 row 2', 'MGP-6 v2: Pilot with a label-determining field', 'FACT', S,
    'mgp6_validity_audit.json: conflict_type, temporal_scope and metadata-tuple lookups give 1.0 on the held-out 90', '')
add(IN, 'Table 1 row 3', 'Answer correctness judged by a model', 'FACT', W,
    RJ + ' lme: not_model_judged 40 (9 correct), scoring_fallback 2 (both correct), judge called 140',
    '40 of 180 verdicts come from deterministic pre-judge guards and 2 judge outputs were unparseable and scored by a substring fallback.',
    'Write "judged by a model with deterministic guards for 40 answers and a substring fallback for 2".')
add(IN, 'Table 1 row 3', 'Exploratory accuracy of one controller on a slice reused from tuning', 'FACT', S,
    'FINAL_ANALYSIS_PLAN.md header', '')
add(IN, 'Table 1 row 4', 'V12 decision log: 12,654 logged decisions', 'NUMBER', S, RJ + ' action_log n 12654', '')

# ------------------------------------------------------------------ interface
add(IF, 'line 8', 'a KEEP on a candidate that has no conflicting prior inserts the candidate as a new active record', 'FACT', S,
    'recovered orchestrator _execute_decision (insert_active unless near-duplicate of the compared prior); action log: 11,464 of 11,478 KEEP rows have resulting_memory_id; the 14 without it all have a prior',
    'KEEP also inserts when a prior exists (686 of 700 such rows), so the condition "no conflicting prior" is narrower than the code.')
add(IF, 'line 9', 'predecessor is retained, marked as superseded, and linked to the successor by an identifier and a relation row, within one database transaction', 'FACT', U,
    'Released src/ask/memory/operations.py lines 83-137 (BEGIN IMMEDIATE, insert, UPDATE status, INSERT memory_relations, COMMIT)',
    'The memory module used in the V12 run is not among the 17 hashed files, so the evaluated version is not identified; the released code supports the sentence.',
    'Attribute to the released code or hash the evaluated module.')
add(IF, 'line 10', 'ABSTAIN: no state change; the record carries no resulting item identifier', 'FACT', S,
    RJ + ' action_log abstain_with_result 0 of 779; _execute_decision returns None for ABSTAIN', '')
add(IF, 'line 15', 'extraction confidence c, evidence quality e, marker burden f (0.5 for each negation or hedge marker), signed relation signal r, stability prior rho', 'FACT', S,
    'src/ask/controller/features.py lines 113-170, 268 (f adds 0.5 per marker; rho 0.9, 0.6, 0.3 for stable, episodic, transient)', '')
add(IF, 'line 15', 'Two scores, S_rev and S_abs, are computed from these features with configured weights', 'FACT', W,
    'src/ask/controller/score.py: s_rev uses ScoreWeights w1-w5; s_abs = (1-c) + f + (1-|r|) has no weights',
    'Only S_rev is weighted.', 'Say "S_rev uses configured weights; S_abs is unweighted".')
add(IF, 'line 15-22', 'action rule: ABSTAIN if S_abs > theta_abs; SUPERSEDE if S_rev > theta_sup and max(0,-r) > 0; otherwise KEEP', 'FACT', S,
    'src/ask/controller/policy.py decide(); independent re-implementation reproduces all 12,654 logged actions', '')
add(IF, 'line 15', 'two-stage language-model relation classifier with deterministic routing', 'FACT', S,
    'relation_trace.jsonl: 9,539 rows with stage1/stage2 prompts and deterministic_routing_reason; escalation not used (relation_escalations 0 in all 180 answers)', '')
add(IF, 'line 23', 'a prior is chosen by embedding similarity (sentence-transformers/all-MiniLM-L6-v2)', 'FACT', S,
    'manifest.embedder.model; answers extras controller_prior_top_k = 3 for 180 of 180; orchestrator _semantic_prior_candidates',
    'The default path (prior_top_k <= 1) picks the newest same-type memory from another session; V12 used top-3 semantic selection.')
add(IF, 'line 23', 'Candidates are produced by a language-model extractor, one turn at a time', 'FACT', S,
    'extraction_trace.jsonl 11,491 rows, each with turn_idx and a model response', '')
add(IF, 'line 26', 'A row holds a timestamp, the action, the candidate text and type, ..., both thresholds, and a rationale string', 'FACT', S,
    'action_log.jsonl key set', 'The log also has id and baseline fields.')
add(IF, 'line 26', 'appended after the database mutation', 'FACT', S,
    'recovered orchestrator: _execute_decision called at line 1667, _write_decision at line 1691', '')
add(IF, 'line 26', 'with a flush to disk for every row', 'FACT', U,
    'Released src/ask/audit/action_log.py: fsync_on_write default True', 'The writer module is not among the 17 hashed files and its history before the 2026-07-25 rename commit was not traced.',
    'Hash the evaluated writer or attribute the statement to the released code.')
add(IF, 'line 26', 'The log is not written atomically with the mutation, so a crash between the two can leave them inconsistent.', 'FACT', S,
    'Separate SQLite mutation and JSONL append in the orchestrator', 'Inference from code structure; no crash was observed.')
add(IF, 'line 26', 'The record does not contain a configuration digest, an evidence digest or before and after state digests', 'FACT', S,
    'action_log.jsonl key set (no digest fields)', '')
add(IF, 'line 29', 'store modes (single-slot versioned, multi-record, temporal-event enumeration value without an implementation); transition function; event; trace; validator; replay scopes; two adapters', 'FACT', S,
    'src/ask/protocol/core.py (StoreMode, ReplayScope, apply_transition, TransitionEvent, DecisionTrace, ASKInvariantValidator); adapters.py (ASKLMEAdapter, ASKMGPAdapter)', '')
add(IF, 'line 31', 'first committed on 2026-08-03, after the LongMemEval run (2026-07-18 to 2026-07-19) and after the MGP-6 v4.3 evaluation code (2026-07-25)', 'NUMBER', S,
    'git log: protocol 2452e97 on 2026-08-03; mgp6_v43.py 41f7cee on 2026-07-25; V12 manifest created 2026-07-18T19:30Z, last action-log row 2026-07-19T09:34Z',
    'src/ask/protocol was later modified (5da4d09, 2026-08-05); the baseline commit is the audited state.')
add(IF, 'line 31', 'No module outside the test suite imports it', 'FACT', S,
    'grep of src, scripts, tests, deploy, benchmarks, configs (phase5_callpath 5.1; re-run here for src, scripts, tests)', '')
add(IF, 'line 32', 'The test suite of 34 tests passes.', 'NUMBER', W,
    'Re-ran tests/test_ask_protocol.py, test_ask_formal_properties.py, test_memory_operations.py, test_temporal.py, test_supersede.py with bytecode and cache writing disabled: 34 passed; the two protocol files contain 10 test functions',
    '34 is a five-file subset that includes memory-operation, temporal and supersede tests, not the repository test suite (postfinal_successor/DEV_CANDIDATE_CONFIG.json records 547 passed, 11 skipped for the full suite).',
    'Write "34 tests in the five files that cover the protocol and the memory operations, 10 of them specific to the protocol".')
add(IF, 'line 32', 'the validator accepted all 19 self-consistent tampering probes, including altered predecessor value or type, unrelated-record deletion or mutation, an unannounced extra record', 'NUMBER', S,
    'VALIDATOR_PROBE_TABLE.csv: S01, S02 (value or type altered), S04, S05 (delete, mutate), S08 (extra record) all ACCEPTED', '')
add(IF, 'line 32', 'and a configuration identity consisting of 64 zeros', 'FACT', C,
    'VALIDATOR_PROBE_TABLE.csv: R01 is a separate replay/configuration-binding probe with observed "ACCEPTED (object constructed)"; PHASE6_VALIDATOR.md counts 19 probes in classes B and C only',
    'The 64-zero identity is not one of the 19 validator probes and was accepted at object construction, not by ASKInvariantValidator.validate.',
    'Move it to the next sentence as a separate observation about the configuration identity.')
add(IF, 'line 32', 'The configuration identity is checked for format only.', 'FACT', S, 'src/ask/protocol/core.py _require_sha256; probe R01', '')
add(IF, 'line 33', 'Transition events are returned in memory and are not persisted by the protocol.', 'FACT', S, 'probe D01: no file or database I/O in ask.protocol.core', '')
add(IF, 'line 33', 'in-memory SQLite database created for each question, so no store survives a run', 'FACT', S,
    'recovered orchestrator line 746 connect(":memory:") in the per-question path; phase5_callpath 5.3', '')
add(IF, 'line 34', 'The adapters are reference code and were not used to produce any reported result.', 'FACT', S, 'import grep; phase5_callpath 5.4', '')

# ------------------------------------------------------------------ MGP-6
add(MG, 'line 4', '180 scenarios, 30 for each of six scenario families, with 90 SUPERSEDE, 66 ABSTAIN and 24 KEEP items', 'NUMBER', S,
    'mgp6_validity_audit.json: n 180, action_counts, type distribution T1-T6 (30 each)', '')
add(MG, 'line 4', 'A lookup fitted on the training and development splits and reading only the conflict type reproduced the held-out actions exactly', 'NUMBER', S,
    'mgp6_validity_audit.json conflict_type.train_dev_lookup: fit_n 90, test_n 90, accuracy 1.0, macro-F1 1.0', '')
add(MG, 'line 7', '900 items in 100 components in 20 domains; train 180 (20), development 180 (20), hidden 540 (60)', 'NUMBER', S,
    HID.replace('hidden_v43', 'construction') + '; FROZEN_CONFIG_INDEX.json; recomputed dev and train: 180 items and 20 components each', '')
add(MG, 'line 7', 'Items are human-authored and template-guided.', 'FACT', U,
    'benchmarks/mgp6/mgp6_v4_3/public/DATASET_CARD.md line 5 (self-description)', 'Only the dataset card asserts authorship; no independent provenance. Annotator identity is flagged in the audit record (CS-16).',
    'Attribute to the dataset card or add authorship provenance.')
add(MG, 'line 7', 'A component has nine items sharing one principal, slot, standing value and proposed value, crossed over three lengths (9, 11, 13) and three gold actions', 'NUMBER', S,
    'Recomputed on public dev and train: 60 (component, length) groups of 3 each; lengths 9, 11, 13 with 60 items each; 20 components each with a single requested value; 3 distinct actions per group', 'Provisional for the full release: hidden components not inspectable (40 of 100 components verified).')
add(MG, 'line 7', 'the dialogue is built from the same pool of six evidence sentences; the three indexed pairs partition the pool (public splits)', 'FACT', S,
    'Recomputed with linked_evidence_view on public dev and train: 120 of 120 groups share one pool of 6 sentences and the three indexed pairs partition it; pools are also identical across the 3 lengths of a component (20 of 20 in dev)', 'Provisional for the full release (public components only). The tracked analysis checked only 80 of 120 triples; the repo router parses all 120.')
add(MG, 'line 7', 'the three actions differ only in which two of the six sentences the dialogue indexes', 'FACT', W,
    'Same recomputation as the abstract row: numbering of the six sentences differs between the three items in 60 of 60 public dev triples',
    'Second location of the "only" statement.', 'Same fix as the abstract row.')
add(MG, 'line 7', 'the same pool and partition for the 60 hidden components', 'FACT', U,
    'Hidden split is private and was not opened', 'The statement is made for all 100 components; only the 40 public components were verified here.', 'Scope the sentence to what was checked, or cite the builder verification.')
add(MG, 'line 7', 'The model-facing record contains an opaque identifier, the stored memory and the dialogue, and no field that names a design target or component.', 'FACT', W,
    'src/ask/eval/mgp6_v43.py MODEL_INPUT_KEYS = (public_id, memory_before, dialogue, evaluation_query); PROHIBITED_MODEL_KEYS',
    'The model-facing record has a fourth field, evaluation_query.', 'Add the evaluation query to the list.')
add(MG, 'line 9', 'five seeds; decision trees of depth 1 to 5; ceilings 0.40 to 0.65; trained on train and evaluated on the component-held-out hidden split', 'NUMBER', S,
    'mgp6_v43_full_benchmark_analysis.json construction.shortcut_audit (seeds 4301-4305, thresholds); build_mgp6_v43_final.py lines 346-383', 'The gate compares the mean accuracy over the five seeds to the ceiling.')
add(MG, 'line 9', 'word and character TF-IDF classifiers on 12 restricted text views', 'FACT', W,
    'build_mgp6_v43_final.py lines 346-359: word TF-IDF on 12 views, character TF-IDF on 2 views',
    'Character n-gram probes cover 2 of the 12 views.', 'Say "word TF-IDF on 12 views and character TF-IDF on 2 views".')
add(MG, 'line 9', 'These checks show that the tested lexical probes did not recover the action', 'FACT', W,
    'Tracked artifacts store only pass/fail gates and ceilings (shortcut_audit_passed true); per-probe accuracies are not stored in the repo',
    'Ceilings reach 0.65, nearly twice the 0.333 chance level, so passing a ceiling does not mean the action was not partly recovered. The probe accuracies are not available to confirm.',
    'Say "stayed at or below preset ceilings (0.40 to 0.65)" and report the per-probe accuracies.')
add(MG, 'line 9', 'cross-split duplicate audit: exact hashes over seven restricted views, character n-gram similarity threshold 0.995, passed', 'NUMBER', S,
    'analysis JSON construction.duplicate_audit; build script lines 418-438; FINAL_RELEASE_VERIFICATION.json duplicate_audit_passed true', '')
add(MG, 'line 11', 'Two annotation packets covered all 900 items and agreed exactly (raw agreement 1.0, kappa 1.0, 300 ambiguity flags raised)', 'NUMBER', S,
    'public/SPLIT_SUMMARY.json human_agreement count 900, rate 1.0, kappa 1.0; RELEASE_FACTS.json annotator_a_count 900, annotator_b_count 900; build script line 736: all 300 flags coincide with ABSTAIN labels',
    'The 300 flags equal the 300 ABSTAIN items, so they add no information beyond the label.')
add(MG, 'line 11', 'perfect agreement shows that the manual is followable and that the items instantiate it', 'CAUSAL', W,
    'analysis JSON annotation_validation.provenance_limit; audit CS-16 (annotator identifiers coincide with dataset-owner name components)',
    'Agreement between two packets whose annotators are not authenticated, and which may not be independent, does not by itself show that a second person can follow the manual. The next sentence concedes the identity gap.',
    'Replace "shows" by "is consistent with".')
add(MG, 'line 11', 'builder validates records, hashes and an owner attestation, but does not authenticate reviewer identity or annotation duration', 'FACT', S,
    'analysis JSON construction.annotation_validation.provenance_limit', '')
add(MG, 'line 15', 'live controller gives a language model the two messages that the public index points to, together with a prompt that states decision criteria', 'FACT', W,
    'src/ask/eval/mgp6_v43.py linked_evidence_view: the view also contains memory_before, requested_value (regex-extracted from the dialogue) and evaluation_query',
    'The description omits the stored memory, the extracted requested value and the query that the model also receives.',
    'List the full view contents.')
add(MG, 'line 15', 'conservative guard that only changes model ABSTAIN outputs when a public-evidence rule resolves them', 'FACT', S,
    'src/ask/eval/mgp6_v43.py apply_live_controller_guard; guard transitions only ABSTAIN->KEEP (30) and ABSTAIN->SUPERSEDE (6)', 'The rule is a hand-written regular-expression policy over the two indexed messages.')
add(MG, 'line 15', 'qwen/qwen3.5-9b through OpenRouter, temperature 0, no reasoning, 128 new tokens, seed 4301', 'NUMBER', S,
    'FINAL_HIDDEN_CONFIG.json hidden_run_controls', '')
add(MG, 'line 15', 'configuration, including the prompt hash, was selected on the public development split and recorded in a hashed manifest before the hidden split was scored', 'FACT', S,
    'FINAL_HIDDEN_CONFIG.json (hidden_run_controls_sha256 1c1d002f...), FROZEN_CONFIG_INDEX.json development_selection; prompt hash recomputed from configs/experiments/mgp6_v43/live_model_controller_prompt.txt matches',
    'The selection run scored 0.8556 on development (DEV_EXPERIMENT_REPORT.md), not 0.844; see consistency row.')
add(MG, 'line 15', 'One complete hidden prediction generation was authorized for the frozen controls.', 'FACT', S,
    'FINAL_HIDDEN_RUN_AUTHORIZATION.json authorization_scope',
    'Omitted detail: FINAL_HIDDEN_EXPERIMENT_REPORT.md records one transport disconnect after 432 predictions and a resume that generated the remaining 108.',
    'Add one clause on the interruption and resume.')
add(MG, 'line 15', 'The hidden split has been consumed, and we have not tuned against it or rerun it.', 'FACT', U,
    'configs/experiments/mgp6_v43/README.md (consumed); postfinal_successor/README.md',
    'No rerun is recorded. A post-final successor configuration (development accuracy 0.95 and 0.9611, tracked in the analysis JSON) was designed after the hidden aggregate was known; it is dev-informed by its own README and is not mentioned in the draft. The negative claim cannot be verified from files.',
    'Disclose the successor in one sentence and state that it was not run on the hidden split.')
add(MG, 'line 15', 'The provider did not report the routed model revision during development', 'FACT', S,
    'FINAL_HIDDEN_CONFIG.json provider_route_limit.routed_model_revision', '')
add(MG, 'line 15', 'The hidden inputs given to the model contained no gold labels', 'FACT', U,
    'FROZEN_CONFIG_INDEX.json hidden_gold_accessed_during_prediction false; hidden_input_policy', 'Record-based; hidden inputs are private and were not inspected.')
add(MG, 'line 15', 'the run authorization required the predictions to be hashed before the private scorer was used', 'FACT', S,
    'FINAL_HIDDEN_RUN_AUTHORIZATION.json post_generation_requirement', '')
add(MG, 'line 15', 'cost-matrix analysis omitted because its weights were committed after the hidden scoring', 'FACT', S,
    'git log: hidden report 7126f46 on 2026-07-26; first tracked occurrence of the v4.3 cost regimes 51decd6 on 2026-08-02; no cost terms in benchmarks/mgp6/mgp6_v4_3 source, protocol or dataset card',
    'Absence-based: weights could have existed in untracked files before the scoring.')
add(MG, 'line 18', 'Accuracy 0.8481 (458 of 540; Wilson 0.8154 to 0.8760)', 'NUMBER', S, HID + ' accuracy, wilson95; recomputed Wilson', '')
add(MG, 'line 18', 'bootstrap over components (60 clusters): accuracy 0.8037 to 0.8889 and macro-F1 0.8021 to 0.8894', 'NUMBER', S,
    HID + ' cluster_ci_acc, cluster_ci_mf1; cluster_bootstrap() in mgp6_v43.py (5,000 replicates, seed 4301)', '')
add(MG, 'line 18', 'Macro-F1 0.8479, MCC 0.7728, kappa 0.7722. No model fallbacks occurred.', 'NUMBER', S, HID + ' macro_f1, mcc, kappa, operational.fallbacks 0', '')
add(MG, 'Table 1 body', 'confusion matrix 151/11/18, 9/165/6, 30/8/142; recall, precision, F1 per class', 'NUMBER', S,
    HID + ' confusion, per_class; column sums 190/184/166 equal reported prediction counts; each row sums to 180',
    'Row and column totals add to 540.')
add(MG, 'line 35', '38 errors on gold-ABSTAIN items (30 KEEP, 8 SUPERSEDE), false-commit rate 0.211 (38 of 180; Wilson 0.158 to 0.276)', 'NUMBER', S, HID + ' safety.false_commit', '')
add(MG, 'line 35', 'Fifteen gold-SUPERSEDE items (0.083) were not superseded, and 11 gold-KEEP items (0.061) were overwritten', 'NUMBER', S, HID + ' safety.missed_update, destructive_overwrite', '')
add(MG, 'line 35', 'Of the 374 items for which the controller did not abstain, 316 were correct (0.845), ... overall accuracy (0.848)', 'NUMBER', S,
    HID + ' selective_coverage 0.6926, selective_accuracy 0.8449; recomputed 374 and 316', '')
add(MG, 'line 35', 'The guard changed 36 of the 202 model ABSTAIN outputs (30 to KEEP and 6 to SUPERSEDE)', 'NUMBER', S, HID + ' guard', '')
add(MG, 'line 38', 'live controller scored 0.844; zero-shot and four structural baselines scored between 0.328 and 0.367', 'NUMBER', S,
    HID.replace('hidden_v43', 'dev_systems') + ' (recomputed rounding of all ten Table 2 rows)', 'Source is the 2026-07-27 complete development rerun (runs/benchmark_suite), see consistency row.')
add(MG, 'line 38', 'only the live controller receives the router-extracted evidence pair; the zero-shot policy and baselines receive the full public payload or a view of it', 'FACT', S,
    'src/ask/eval/mgp6_v43.py model_input_for_system (b1 dialogue only, b2 flat memory + dialogue, b3 memory + last 2 turns, others full payload)', '')
add(MG, 'line 38', 'the live controller also receives a different, longer prompt', 'FACT', S,
    'configs/experiments/mgp6_v43/live_model_controller_prompt.txt (933 bytes) versus decision_system_prompt.txt (79 bytes)', '')
add(MG, 'line 38', 'the four component ablations receive the full payload with their own prompts', 'FACT', W,
    'model_input_for_system: ablation_no_provenance receives dialogue text without speaker and turn identifiers plus memory_before; the other three fall in the default branch (full payload)',
    'Three of the four receive the full payload; no-provenance receives a stripped view.', 'Write "three receive the full payload and no-provenance receives the dialogue without provenance".')
add(MG, 'Table 2', 'ten rows of accuracy and macro-F1', 'NUMBER', S,
    HID.replace('hidden_v43', 'dev_systems') + ': all 20 values equal the JSON values rounded to 3 decimals', '')
add(MG, 'line 62', 'substitute model (gemini-3.8-flash at low reasoning through a gateway, temperature 0, two repeats), four cells on the 180 public development items', 'FACT', S,
    'phase13 results.jsonl: 1440 rows = 180 x 4 cells x 2 repeats; requested ag/gemini-3.8-flash-low, returned gemini-3.8-flash on all rows; reasoning tokens present; HTTP 200 on all rows', '')
add(MG, 'line 62', 'Because the manuscript model was not available to us at that time', 'FACT', S,
    'RESEARCH_DECISIONS.md D14; phase16 README_RUN.md ("qwen/qwen3.5-9b is not in the gateway lists")', 'The reason is gateway availability, not model availability in general.')
add(MG, 'Table 3 top', 'accuracies 0.772/0.750, 0.878/0.883, 0.811/0.772, 0.889/0.894', 'NUMBER', S, 'Recomputed from phase13 results.jsonl against dev.jsonl labels', '')
add(MG, 'Table 3 bottom', 'contrasts +0.119 [0.047, 0.192], +0.100 [0.039, 0.164], +0.031 [-0.017, 0.081], +0.011 [-0.031, 0.053]', 'NUMBER', S,
    'Recomputed: paired item-level bootstrap, 10,000 resamples, seed 0 (' + RJ + ' twobytwo.contrasts)', '')
add(MG, 'line 62', 'live prompt associated with a gain of 0.10 to 0.12; routing 0.03 with the one-line prompt and 0.01 with the live prompt, intervals include zero', 'NUMBER', S,
    'contrasts above', '')
add(MG, 'line 62', 'abstention recall rose (from 24 to 57 of 60 ...) while supersession recall fell (from 58 to 44 of 60)', 'NUMBER', S,
    'Confusion matrices repeat 0 recomputed: cell A abstain row 30/6/24, supersede row 2/58/0; cell E abstain row 3/0/57, supersede row 0/44/16', '')
add(MG, 'line 62', 'the substitute model scored 0.75 to 0.77 where the manuscript model was near chance', 'NUMBER', S,
    'cell A 0.750 and 0.772; Table 2 zero-shot 0.339 against chance 0.333', 'The substitute model used reasoning tokens while the qwen runs used reasoning none; this uncontrolled difference is not stated here.')
add(MG, 'line 62', 'With either evidence view, the live prompt was associated with a gain', 'ROLE_MIXING', W,
    'phase13 report 13.3: the live prompt states that the input holds exactly two indexed messages; in the full-payload cell the input does not',
    'The full-payload by live-prompt cell is a mismatched condition (prompt text describes a view the model does not receive). The report labels it a diagnostic cell; the draft does not.',
    'State that the full-payload by live-prompt cell uses a prompt whose text assumes the routed view.')
add(MG, 'line 62', 'The effects look approximately additive.', 'CAUSAL', W,
    'Differences: prompt +0.119 (full) versus +0.100 (routed); routing +0.031 versus +0.011; no interaction test or interval',
    '"Effects" is causal wording for a four-cell comparison on one model; additivity was not tested.', 'Write "the differences are similar across levels of the other factor".')
add(MG, 'line 62', 'item-level bootstrap intervals that ignore the grouping into components, so they are likely too narrow', 'FACT', S,
    'dev.jsonl has no component identifier; phase13 13.6', '')
add(MG, 'line 62', 'the development split is the split on which the live prompt was selected, so cells with the live prompt are optimistic', 'FACT', S,
    'FROZEN_CONFIG_INDEX.json development_selection.selection_basis: public dev only', '')
add(MG, 'Figure 1', 'plotted points and lines (repeat values and means)', 'CONSISTENCY', S,
    'Visual read of figures/fig_twobytwo.png: points at 0.772/0.750, 0.878/0.883, 0.811/0.772, 0.889/0.894; line ends at the repeat means 0.761, 0.792, 0.881, 0.892',
    'Matches Table 3. The y-axis starts at 0.70, which is acceptable for a point plot.')

# ------------------------------------------------------------------ LME
add(LM, 'line 4', '180-question slice stratified at 30 questions for each of the six question types', 'NUMBER', S, RJ + ' lme.n_per_competency: 30 each', '')
add(LM, 'line 4', 'answer model qwen/qwen3.5-9b with reasoning disabled; judge google/gemma-4-31b-it', 'FACT', S,
    'V12 manifest.json: answer_model, answer_provider_policy.reasoning_enabled false, judge_primary; judgments judge_model_id', '')
add(LM, 'line 4', 'candidates were extracted turn by turn from the question\'s sessions into a fresh in-memory store for each question', 'FACT', S,
    'extraction_trace.jsonl; orchestrator connect(":memory:") per question', '')
add(LM, 'line 4', 'eight shards, resumed twice, exit code 1, status never changed from running', 'FACT', S,
    'manifest.json: shards 8, attempts 3 (two resumes), exit_code 1, status running', '')
add(LM, 'line 4', 'a homogeneity check that we describe below returned false', 'FACT', S,
    'homogeneity_report.json homogeneous false', 'True as stated, but see the row on the reason given below.')
add(LM, 'line 4', 'The answer provider policy allowed fallback among three providers, and the provider that served each call was not reported', 'FACT', S,
    'manifest answer_provider_policy: allow_fallbacks true, only venice, deepinfra, siliconflow; homogeneity_report actual_answer_providers unreported 31,244', '')
add(LM, 'line 4', 'The slice had been used to tune the preceding controller version', 'FACT', W,
    'FINAL_ANALYSIS_PLAN.md header; backup runs_local/controller_v12_guard_20260718 contains run_guard2 to run_guard11 (10 directories) plus run, run_fixed and run_shared_embed; its input files hold 15, 8 and 4 questions, all within the 180-question slice (ids compared as set membership only)',
    'The plan says V12 was selected after inspecting partial V11 outcomes on this slice. The backup also shows V12 guard iterations on slice questions on 2026-07-18, so tuning reaches V12 itself. This is a provisional inference from directory structure; the content was not read.',
    'Say "used to select and tune the V11 and V12 controller versions".')
add(LM, 'line 4', 'the analysis plan frozen before the run states ... descriptive and exploratory', 'FACT', S,
    'FINAL_ANALYSIS_PLAN.md lines 1-6; plan sha256 690b54b2 equals the hash recorded in the run manifest at creation', '')
add(LM, 'line 4', 'The run\'s acceptance target of 153 of 180 correct answers was not met.', 'NUMBER', S, 'manifest controller_accuracy_acceptance required_correct 153; counts 128 and 137', '')
add(LM, 'line 7', 'The judge scored 128 of 180 answers as correct (0.711) ... 137 of 180 (0.761)', 'NUMBER', S, RJ + ' lme correct_raw, correct_final', 'Arithmetic only; see next row for the attribution to "the judge".')
add(LM, 'line 7', 'The judge scored 128 of 180 answers as correct', 'FACT', W,
    RJ + ' lme: judge_was_called false for 40 answers (9 of them correct); 2 judge outputs unparseable and scored by normalized substring fallback (both correct); homogeneity_report deterministic_guards 40, scoring_fallbacks 2',
    'Of the 128, 9 come from deterministic pre-judge guards, 2 from a substring fallback and 117 from parsed model-judge verdicts.',
    'State the three scoring paths and the counts per path.')
add(LM, 'line 7', 'Exact (Clopper-Pearson) 95% intervals 0.639 to 0.776 for 128 of 180 and 0.692 to 0.821 for 137 of 180', 'NUMBER', S, RJ + ' lme.clopper_pearson', 'Treats the stratified slice as one binomial sample.')
add(LM, 'line 7', 'The nine abstention questions were answered correctly in eight cases.', 'NUMBER', S,
    RJ + ' lme: 9 session ids with the abstention suffix; 8 correct before and after adjudication', 'Definition by identifier suffix.')
add(LM, 'line 7', 'the answer model is a hosted service whose generation seed was not set', 'FACT', C,
    'answers.jsonl seed 0 in 180 of 180 records; homogeneity_report seeds ["0"]; recovered orchestrator passes seed=self.seed to the answer call; openai_compatible.py adds payload["seed"] when seed is not None; FINAL_RUN_MATRIX.yaml seed 0',
    'A request seed of 0 was configured and sent. Whether the hosted provider honors it is unknown. The audit record "seed null" predates the raw-evidence phase.',
    'Write "a request seed of 0 was sent, but provider-side determinism is not established".')
add(LM, 'Table 4', 'per-type counts 29/29, 19/19, 29/29, 9/16, 24/25, 18/19; totals 128/137', 'NUMBER', S,
    RJ + ' lme.by_competency_raw and by_competency_final; column sums 128 and 137', '')
add(LM, 'line 29', 'Nine judgments were changed by hand from incorrect to correct; all concern the controller; none in the other direction; seven in single-session-preference', 'NUMBER', S,
    RJ + ' lme: adjudicated 9, pre-adjudication all incorrect; by competency 7, 1, 1; baselines carry no adjudicated flag', '')
add(LM, 'line 29', 'A script records a short written reason for each change and keeps the original judge output in a backup file', 'FACT', S,
    'adjudication_note present for 9 of 9 (length 69-144 characters; content not read); .pre_manual_adjudication.orig files in shards; judge_raw_output_pre_adjudication in 8 of 9', '')
add(LM, 'line 29', 'We did not review the failures of any other system by the same criteria', 'FACT', U,
    'phase15 15.5: no equivalent review recorded', 'Negative process claim; absence of a record is not proof. Three undocumented baseline overrides exist.')
add(LM, 'line 29', 'plan asks that results be reported on the raw judge score first and any adjudication as a separate sensitivity analysis', 'FACT', S,
    'FINAL_ANALYSIS_PLAN.md lines 100-101 and 140-141', '')
add(LM, 'line 29', 'concentration suggests that the model judge and the human reader disagree most where the reference is a preference description', 'CAUSAL', W,
    RJ + ' lme.raw_failures_by_competency: 21 of 52 raw failures are in single-session-preference; find_cases.py selects a fixed list of target ids',
    'The nine cases were selected by a script; coverage of the other 43 failures is not recorded. Concentration may reflect where failures and reviewer attention were concentrated.',
    'Say that seven of nine reviewed cases were in that type, and that review coverage of other failures is not documented.')
add(LM, 'Figure 2', 'correct answers out of 30 per type before and after adjudication', 'CONSISTENCY', S, 'Visual read of figures/fig_lme.png against Table 4: all twelve values equal', '')
add(LM, 'line 38', 'baselines with 9, 80, 43 and 114 correct answers; byte-identical to the baselines of an earlier run', 'NUMBER', S,
    RJ + ' baselines: counts; identical_to_providerpool true for the four judgments files (sha256)', '')
add(LM, 'line 38', 'earlier run used a different freeze version, shard layout and judge configuration (free tier with a fallback)', 'FACT', S,
    'providerpool manifest: freeze final-1.3, 20 shards, judge_primary google/gemma-4-31b-it:free, fallback google/gemma-4-31b-it; V12: final-2.0, 8 shards, no fallback', '')
add(LM, 'line 38', 'model identifiers for the baselines differ in form (a dated slug versus an undated identifier)', 'FACT', S,
    'b1-b4 answers model_id qwen/qwen3.5-9b-20260310; controller answers qwen/qwen3.5-9b', '')
add(LM, 'line 38', 'its run matrix says that it does not support comparative claims and defines a separate five-system run', 'FACT', S,
    'recovered FINAL_RUN_MATRIX.yaml lines 22-34 and 74', '')
add(LM, 'line 38', 'Three baseline judgments carry override fields that no available code writes', 'FACT', S,
    RJ + ' baselines: b1 1 (correct to incorrect), b4 2 (incorrect to correct); grep of 17 recovered files, released src/scripts/tests and the three adjudication scripts finds no judge_overridden', '')
add(LM, 'line 38', 'The homogeneity check required by the plan ... therefore failed', 'CAUSAL', C,
    'homogeneity_report.json: systems checked [controller] only; per-system errors []; global_errors only "manifest code/protocol hash stale: scripts/evaluation/run_longmemeval_final.sh"; verify_homogeneous_run.py lines 440-470',
    'The recorded false is caused by a stale launcher hash in a controller-only check. Baseline heterogeneity was found by the audit, not by this check, and the plan-required five-system check was never run.',
    'Say that the check as recorded returned false for a stale-hash reason, and that the baseline heterogeneity was identified separately.')
add(LM, 'line 41', '12,654 decisions from 3,547 sessions: 11,478 KEEP (0.907), 397 SUPERSEDE (0.031), 779 ABSTAIN (0.062)', 'NUMBER', S, RJ + ' action_log', '')
add(LM, 'line 41', '9,857 episodic facts, 2,416 transient preferences and 381 stable preferences', 'NUMBER', S, RJ + ' action_log.types; sum 12,654', '')
add(LM, 'line 41', 'All 397 supersessions carry a predecessor and a successor identifier; no abstention row carries a resulting identifier; 11,464 of 11,478 KEEP rows carry one', 'NUMBER', S, RJ + ' action_log', '')
add(LM, 'line 43', 'All 12,654 actions matched, recomputed scores and thresholds matched with a maximum absolute deviation of 0.0; bound to the log SHA-256', 'NUMBER', S,
    RJ + ' action_log.r1_mismatches 0, r1_max_abs_dev 0.0, sha256 08ebd013...; matches artifacts/manifests/lme_v12_derived_manifest.json output_sha256', 'My re-implementation was written from the released code; it is a consistency check, not an independent specification.')
add(LM, 'line 43', 'The scorecard modules are not among the files whose hashes the run manifest recorded', 'FACT', S,
    'manifest code_and_protocol_sha256 lists 17 files; policy.py, score.py, features.py absent', '')
add(LM, 'line 45', '11,771 validated extracted items from 11,491 processed turns; the log holds 883 more decisions than items', 'NUMBER', S,
    RJ + ' extraction: 11,491 trace rows, 11,771 validated items (13 rows with no validated output; cache has 11,477 entries); 12,654 - 11,771 = 883', '')
add(LM, 'line 45', '88 rows repeat a (session, candidate identifier) pair, and 1,277 candidate texts receive more than one decision, mostly under different candidate identifiers', 'NUMBER', S,
    RJ + ' action_log: 88; 1,277 groups under key (session, type, text), 1,227 with different candidate ids, 51 with different actions',
    'The 1,277 figure requires the key (session, candidate type, text); keyed on text alone across sessions it is 1,447. The key is not stated.',
    'State the grouping key.')

# ------------------------------------------------------------------ discussion
add(DI, 'line 3', 'The decision record and its R1 replay are verified on one log.', 'FACT', S, 'Replay recomputation above; R2 to R7 not claimed', '')
add(DI, 'line 3', 'one frozen configuration separates the three actions ... with an accuracy near 0.85', 'NUMBER', S, HID, 'Wording "separates" is stronger than 0.848 accuracy with 82 errors; see wording row.')
add(DI, 'line 3', 'with most errors being gold-ABSTAIN items that were committed', 'NUMBER', C,
    RJ + ' hidden: errors by gold class KEEP 29, SUPERSEDE 15, ABSTAIN 38 of 82 (46.3%)',
    'The largest share is 46%, not a majority.', 'Write "the largest share of errors (38 of 82)".')
add(DI, 'line 3', 'The LongMemEval run shows that the controller answered 128 of 180 questions correctly under the judge', 'FACT', W,
    'See the scoring-path row (40 guard verdicts, 2 fallbacks)', 'Same attribution issue as Section 5.')
add(DI, 'line 3', 'one frozen configuration separates the three actions', 'CAUSAL', W,
    'Project wording rule (audit word "separates")', 'Discriminative claim stated without a baseline in the same conditions; the paper itself says no matched comparison exists.',
    'Use "classifies the three actions with accuracy 0.848".')
add(DI, 'line 5', 'run manifest records hashes of 17 code and protocol files, all of which we recovered from repository history and object storage', 'NUMBER', S,
    'sha256 of the 17 files in recovered_evaluated_code.tar.gz equals manifest values (17 of 17)', '')
add(DI, 'line 5', 'evaluated orchestrator differs from the released one by about 900 changed lines and a different class structure', 'NUMBER', S,
    'difflib on recovered versus working-tree orchestrator after ksa-to-ask normalization: 916 changed lines; classes _AnswerState, _CacheCounters, _IngestionResult, _PreparedAnswer absent from the evaluated file; build_jinja_env absent from the released file', '')
add(DI, 'line 7', 'the controller on the hidden split never receives the distractor sentences; the pool check holds by construction', 'FACT', S,
    'linked_evidence_view returns only the two indexed snippets; pool and partition recomputation on public splits', '')
add(DI, 'line 9', 'the generation seed was unset', 'FACT', C, 'Same evidence as Section 5 seed row', 'Second location of the seed statement.', 'See Section 5 fix.')
add(DI, 'line 9', 'the adjudication was applied to one system', 'FACT', W,
    RJ + ' baselines: three override fields in b1 and b4',
    'Manual adjudication was applied to one system, but three baseline verdicts were overridden by an undocumented process.', 'Add "and three baseline verdicts carry undocumented overrides".')
add(DI, 'line 9', 'the run was executed once', 'FACT', W,
    'manifest attempts: 3 invocations; backup holds controller runs V9 (two), V10, V11 and the V12 guard-iteration directories (run_guard2 to run_guard11) on slice questions',
    'The final configuration was run to completion once after two resumes, but not the first run on this slice.', 'Say "the final configuration was run once (after two resumes)".')
add(DI, 'line 9', 'seven of the nine manual corrections fell in one question type', 'NUMBER', S, RJ + ' lme.adjudicated_by_competency', '')

add(DI, 'line 5', 'defines a temporal mode without an implementation; evaluated store was an in-memory database per question', 'FACT', S,
    'probe K05 (TEMPORAL_EVENT behaves as unconstrained multi-record); recovered orchestrator connect(":memory:")', '')
add(DI, 'line 7', 'MGP-6 v4.3 materializes no memory state', 'FACT', S, 'src/ask/eval/mgp6_v43.py scores actions only; phase5_callpath 5.4', '')
add(DI, 'line 7', 'The 2x2 decomposition used a substitute model and the prompt-selection split, ignores component clustering, and does not identify which part of the prompt matters', 'FACT', S,
    'phase13 13.6; dev.jsonl has no component identifier; prompt factor is a bundle (13.3)', '')
add(DI, 'line 7', 'A high score measures the ability to apply the decision criteria to the indexed evidence, not to find the relevant evidence', 'CAUSAL', S,
    'linked_evidence_view routes the indexed pair; guard is a regular-expression policy over the same pair; labels are a function of the indexed pair by construction',
    'Interpretation consistent with the construction; the guard rules, not only the model, contribute to the score (guard changed 36 of 540 final predictions).')

# ------------------------------------------------------------------ conclusion
add(CO, 'line 3', 'accuracy of 0.848 ...; 128 correct answers on the judge\'s scoring and 137 after nine manual adjudications; 12,654-row decision log', 'NUMBER', S, 'As above', '')
add(CO, 'line 3', 'a validator and a persistence layer that are incomplete', 'FACT', W,
    'probe D01: ask.protocol.core performs no file or database I/O; phase5 5.4: no event sink exists',
    '"Incomplete persistence layer" implies a partial layer; none exists.', 'Write "a validator that accepts non-conforming states and no persistence layer".')

# ------------------------------------------------------------------ appendix
add(AP, 'App. A line 4', 'judgments and report of the controller, its action log, and the judgments of the four baselines match the SHA-256 values in the repository derived manifest', 'FACT', W,
    'lme_v12_derived_manifest.json output_sha256 lists b4 judgments, b4 report and the controller judgments, report and action log; b1, b2, b3 judgments are recorded in artifacts/analysis/lme_v12_adjacent_mcnemar.json (source_sha256); all hashes recomputed and equal',
    'The derived manifest covers only b4 among the baselines.', 'Name both files.')
add(AP, 'App. A line 4', 'All 17 were recovered by hash; seven are reachable from commits and ten exist only as objects that no current branch or tag references', 'NUMBER', S,
    'sha256 of the 17 recovered files equals manifest hashes; git rev-list --all --objects on the backup repository: 7 blobs reachable from refs, 10 not (read-only)', 'The 10 are also unreferenced by any other ref.')
add(AP, 'App. A line 4', 'released orchestrator, longmemeval module, computation module and inference client differ from the recovered versions', 'FACT', S,
    'diff line counts: 916, 16, 129, 298', '')
add(AP, 'App. A line 4', 'frozen analysis plan, protocol, metric definitions and run matrix carry the hashes recorded at run time', 'FACT', S, 'sha256 match, 4 of 4', '')
add(AP, 'Table B, R1', 'Established: all 12,654 actions and scores recomputed', 'NUMBER', S, 'See Section 5 replay row', '')
add(AP, 'Table B, R2 to R5', 'R2 not established: SQLite statements, no state digests; R3 partial, reference code only; R4 store in memory; R5 not established', 'FACT', S, 'phase7_replay_persistence/REPLAY_LEVELS.csv; action-log key set', '')
add(AP, 'Table B, R6', 'Not established: hosted model, generation seed not set', 'FACT', C, 'Same seed evidence as Section 5', 'Third location of the seed statement; the "not established" status holds, the reason does not.',
    'Write "hosted model; request seed 0 sent; provider determinism not established".')
add(AP, 'Table C', 'B1 9, B3 43, B2 80, B4 114 (112 before the two undocumented overrides)', 'NUMBER', S, RJ + ' baselines', '')
add(AP, 'Table C, B1 row', 'B1 no memory: 9, earlier run', 'CONSISTENCY', W,
    RJ + ' baselines.b1: 1 override (10 before, correct to incorrect)',
    'The table flags the B4 overrides but not the B1 override, while the text (Section 5) lists three.', 'Add "(10 before one undocumented override)" to the B1 row.')
add(AP, 'Table D, row 7', 'The protocol validates conforming states - Not supported - 19 of 19 tampering probes accepted', 'FACT', C,
    'PHASE6_VALIDATOR.md: 4 builder-produced controls were accepted; 19 tampered states were accepted',
    'Accepting tampered states shows the validator does not reject non-conforming states. It does not show that conforming states are rejected; the controls were accepted. The claim and its basis do not match.',
    'Rewrite as "The validator rejects non-conforming states - Not supported - 19 of 19 tampering probes accepted".')
add(AP, 'Table D, rows 1-6, 8', 'status of other claims', 'FACT', S, 'Checked against rows above', 'Row 1, 4, 6 values verified; rows 2, 3, 5, 8 are scope statements consistent with the evidence.')

# ------------------------------------------------------------------ related work spot check
add(RW, 'line 43', 'The 30 comparators were read in full text ... 12 search-surfaced candidates were coded on four elements only', 'NUMBER', S,
    'phase3_8_literature/*/FEATURE_ROWS.csv: 6+8+5+5+6 = 30 rows; SATURATION_CANDIDATES_SUMMARY.csv: 12; SATURATION_STATEMENT.md known gaps', '')
add(RW, 'line 45', '30 full-text comparators, 12 search-surfaced candidates and 112 targeted search iterations', 'NUMBER', S,
    'SEARCH_LOG.csv has 118 rows = 112 discovery iterations + 6 identifier-resolution steps (SATURATION_STATEMENT.md)', '')
add(RW, 'line 45', 'whose search record is released', 'FACT', U, 'No release record in the evidence files', 'Depends on publication of SEARCH_LOG.csv.', 'Cite the location of the released log when known.')
add(RW, 'line 45', 'we did not identify a system ... that implements all of the following (five elements)', 'NOVELTY', S,
    'PHASE8 8.5(2) uses the same five-part conjunction; SATURATION_STATEMENT.md screened the 12 new candidates on four elements',
    'Bounded wording is used. The 12 search-surfaced candidates were screened against four broader elements, so the five-part conjunction is excluded for them by implication, not by direct coding.')

# ------------------------------------------------------------------ consistency and wording
add('multiple files', 'cross-file', 'dev live-controller accuracy 0.844 in Table 2 versus the selected development candidate', 'CONSISTENCY', W,
    'FROZEN_CONFIG_INDEX.json public_dev_metrics 0.8556/0.8566 and DEV_EXPERIMENT_REPORT.md (selection run 54c8c72); analysis JSON dev_systems 0.8444/0.8458 (complete rerun recorded 2026-07-27)',
    'The repository holds two development results for the live controller and different values for several baselines (for example zero-shot 0.3333 versus 0.3389, B3 0.3389 versus 0.3278, no-abstention macro-F1 0.2398 versus 0.2465). The draft reports only the rerun values and calls them "tracked results" without naming the run.',
    'Name the source run in the Table 2 caption and state the selection-run value.')
add('multiple files', 'cross-file', 'Same quantity in abstract, introduction, body, tables, figures and conclusion', 'CONSISTENCY', S,
    '0.848, 540 hidden, 60 components, 128/137, 12,654, 19 probes, 17 files: identical in all locations',
    'Exceptions are the seed statement (consistent across three places but contradicted) and the B1 override omission in Table C.')
add('multiple files', 'cross-file', 'em dashes', 'WORDING', S,
    'Scan of main.tex and sections 00-08 for U+2014, U+2013 and TeX "---": none; "--" occurs once in Clopper--Pearson (an en dash in a name)', '')
add('multiple files', 'cross-file', 'forbidden words: first (priority), unique, unprecedented, novel, state of the art, solves, safe, production-ready', 'WORDING', S,
    'Regex scan of all section files: "first" occurs only as an enumerator or a chronology term; the other words are absent; "new" occurs once in the claims table under "Not claimed"', '')
add('multiple files', 'cross-file', 'evidence-role mixing between synthetic action labels, downstream answers, replay and memory state', 'ROLE_MIXING', S,
    'Read of all sections against Table 1: no sentence presents MGP-6 action accuracy as validating downstream answers; replay is presented as R1 only; the answer score is explicitly separated from memory state',
    'The two role issues found are the "development gain" wording (abstract) and the cell E mismatch (Section 4).')

# ------------------------------------------------------------------ write
for i, r in enumerate(R, 1):
    r['id'] = f'CC-{i:03d}'
    assert len(r['excerpt'].split()) <= 25, (r['id'], len(r['excerpt'].split()))
    for k in ('excerpt', 'ev', 'note', 'fix'):
        assert '\u2014' not in r[k], r['id']

cols = ['id', 'file', 'line_or_locator', 'claim_excerpt', 'category', 'verdict', 'evidence_checked', 'note', 'proposed_fix']
with open(os.path.join(OUT, 'CLAIM_CHECK_REPORT.csv'), 'w', newline='', encoding='utf8') as f:
    w = csv.writer(f)
    w.writerow(cols)
    for r in R:
        w.writerow([r['id'], r['file'], r['loc'], r['excerpt'], r['cat'], r['verdict'], r['ev'], r['note'], r['fix']])

cnt = collections.Counter(r['verdict'] for r in R)
cat = collections.Counter((r['cat'], r['verdict']) for r in R)
print(len(R), dict(cnt))
print(sorted(cat.items()))


# ------------------------------------------------------------------ summary
def line(r):
    fix = f" Fix: {r['fix']}" if r['fix'] else ''
    return f"- {r['id']} | {r['file']} | {r['loc']} | {r['cat']} | claim: \"{r['excerpt']}\" | {r['note']}{fix}"


def section(verdict):
    return [line(r) for r in R if r['verdict'] == verdict]


tot = len(R)
vc = collections.Counter(r['verdict'] for r in R)
cc = collections.defaultdict(collections.Counter)
for r in R:
    cc[r['cat']][r['verdict']] += 1
L = []
L.append('# Claim check summary')
L.append('')
L.append('Independent claim check of the arXiv draft (main.tex and sections 00, 01, 03 to 08; closing paragraph of section 02 only). Report only; no draft file was edited. Evidence was read from the tracked repository at baseline commit f6bf66e, the audit record, and the owner backup of the V12 run directory (read only). Benchmark text was never printed, copied or saved: only counts, booleans, hashes and field lengths were computed.')
L.append('')
L.append('## Declared reductions and process notes')
L.append('')
L.append('- Section 02 was checked only for its closing "Scope of the comparison" paragraph and the line above it, as instructed. Table cells, citations and the bibliography (other than the LongMemEval entry) were not checked.')
L.append('- The hidden MGP-6 split, its gold labels and its model-facing inputs are private and were not opened. Hidden-split structure claims (pool sharing, partition, no gold in inputs) are therefore UNVERIFIABLE here; public train and dev were recomputed instead (40 of 100 components).')
L.append('- The 950 MB LongMemEval slice file, answers, predictions and judge rationales were not opened for content. Question types come from the judgments competency field; abstention questions are identified by the identifier suffix; adjudication notes were measured by length only.')
L.append('- Figures were checked by viewing the PNG renderings against Tables 3 and 4, not by extracting plotted data from the PDF.')
L.append('- The full repository test suite was not run. The five test files named in the Phase 6 record were run with bytecode and cache writing disabled (34 passed); git status was unchanged afterwards.')
L.append('- Git reachability of the 17 recovered blobs was checked with read-only commands on the backup repository (rev-list over all refs).')
L.append('- The finding that V12 guard rules were iterated on slice questions rests on directory names and set membership of identifiers only (provisional, inference from structure).')
L.append('- No paid API, web search or network call was made.')
L.append('- Process note: early in the work I wrote a scratch copy of three draft sections into the draft folder by mistake (draft_rest_tmp.txt). It was a copy, no draft file was altered, and it was moved to the Trash with the owner approval prompt.')
L.append('')
L.append('## Counts')
L.append('')
L.append(f'Rows in CLAIM_CHECK_REPORT.csv: {tot}')
L.append('')
L.append('| Verdict | Count |')
L.append('|---|---:|')
for v in (S, W, C, U):
    L.append(f'| {v} | {vc[v]} |')
L.append('')
L.append('| Category | SUPPORTED | WEAKER_THAN_STATED | CONTRADICTED | UNVERIFIABLE |')
L.append('|---|---:|---:|---:|---:|')
for k in sorted(cc):
    L.append(f"| {k} | {cc[k][S]} | {cc[k][W]} | {cc[k][C]} | {cc[k][U]} |")
L.append('')
L.append('## Highest-impact findings (all in the lists below)')
L.append('')
L.append('1. The statement that the generation seed was not set is contradicted in three places (Section 5 results, Discussion limitations, Appendix R6). The answer records, the homogeneity report, the run matrix and the evaluated code all show a request seed of 0.')
L.append('2. "The judge scored 128 of 180" mixes three scoring paths: 117 parsed model-judge verdicts, 9 correct verdicts from deterministic pre-judge guards (40 answers were never sent to the judge), and 2 substring-fallback verdicts after unparseable judge output.')
L.append('3. The homogeneity check recorded as false was a controller-only check that failed on a stale launcher hash. The draft attributes the failure to baseline heterogeneity, which the audit found separately.')
L.append('4. Discussion says most hidden errors are gold-ABSTAIN items committed; the share is 38 of 82 (46%).')
L.append('5. The abstract\'s "development gain" is the +0.13 gain of the substitute model, not the +0.505 gain in Table 2; the full-payload by live-prompt cell uses a prompt that describes a routed view the model does not receive.')
L.append('6. "Differ only in which two of six sentences are indexed" is not supported: the numbered order of the six sentences also differs between the three actions in all 60 public dev triples.')
L.append('7. The 64-zero configuration identity is not one of the 19 validator probes, and the Appendix claim row "The protocol validates conforming states" has a basis that points the other way (the four builder controls were accepted).')
L.append('8. Table 2 reports the later complete development rerun (live controller 0.844); the selection run recorded in the repository scored 0.8556, and several baselines differ between the two runs. The draft does not say which run it reports.')
L.append('')
L.append('## CONTRADICTED')
L.append('')
L.extend(section(C))
L.append('')
L.append('## WEAKER_THAN_STATED')
L.append('')
L.extend(section(W))
L.append('')
L.append('## UNVERIFIABLE')
L.append('')
L.extend(section(U))
L.append('')
L.append('## What was not checked, and why')
L.append('')
L.append('- Correctness of feature extraction, relation classification, memory state or answers in the V12 run: no state was persisted, and the draft does not claim it (replay levels R2 to R7).')
L.append('- Whether a hosted provider honors a request seed: not observable from files.')
L.append('- Annotator independence and authorship of MGP-6 items: no independent provenance exists in the evidence set (audit finding CS-16).')
L.append('- Existence of a released search log and of the figures in the final PDF: not part of the evidence set.')
L.append('- Related-work classifications of individual comparators and their citations: out of scope by instruction.')
L.append('- Whether the post-final successor configuration influenced design choices through knowledge of hidden aggregates: not decidable from files; it is listed as an undisclosed item.')
L.append('- LaTeX compilation, reference resolution and typography: not checked.')
L.append('')
L.append('## Files')
L.append('')
L.append('- CLAIM_CHECK_REPORT.csv: one row per checked claim (columns as specified).')
L.append('- claimcheck_recompute.py and claimcheck_recomputed.json: aggregate-only recomputation of the numbers used (no benchmark text).')
L.append('- build_claimcheck_report.py: generates the CSV and this summary from the row definitions.')
open(os.path.join(OUT, 'CLAIM_CHECK_SUMMARY.md'), 'w', encoding='utf8').write('\n'.join(L) + '\n')
assert '\u2014' not in '\n'.join(L)
print('summary written')
