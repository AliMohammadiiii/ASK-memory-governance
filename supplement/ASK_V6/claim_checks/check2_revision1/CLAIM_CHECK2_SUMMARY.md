# Claim check 2 (revision 1 of the arXiv draft)

Independent claim check of main.tex, sections 00, 01, 03 to 08 and the two model tables. Report only: no draft file and nothing under the ASK-memory-governance repository was edited. Evidence was read from the repository at baseline commit f6bf66e (exported with git archive to /tmp, read only), the Phase 4 to 16 audit record, raw per-call result rows of the decomposition runs (public development items only), and the V12 backup run directory (aggregates only).

## Items I could not check, or checked only partly (read first)

1. Section 2 (related work), its table and the bibliography beyond key presence were not checked; the claim "each element has prior or concurrent precedent" is therefore UNVERIFIABLE here (CC2-ABS-13, CC2-INT-11).
2. The 60 hidden MGP-6 components, the hidden model inputs, hidden predictions and the per-probe shortcut accuracies are private or not tracked. Hidden-split numbers were taken from the tracked analysis json (artifacts/analysis/mgp6_v43_full_benchmark_analysis.json) and the confusion matrix in it; the cluster bootstrap intervals were not recomputed (the private component map was not opened). Pool structure was recomputed on the 40 public components only (CC2-MGP-09, CC2-MGP-14).
3. The 950 MB LongMemEval slice, answers, predictions and rationales were not opened. Judgment files were read for counts and flags only; no benchmark text is in any output.
4. The request body of the V12 answer calls is not logged, so "seed 0 was sent" rests on the recovered client code and the seed field of the predictions (CC2-LME-08). What the 9Router gateway adds to the Phase 16 requests cannot be tested; the 2,000 token overhead is an estimate by regression-free differencing.
5. The full repository test suite was not run; five test files (34 tests) were. The git reachability of the 17 recovered code blobs and the byte identity of all baseline shard files were taken from Phase 15 (I recomputed the SHA-256 of the six top-level files named in CC2-APP-01 and of b1 to b4 judgments against the earlier run).
6. The raw rows of the Kimi K2.5 and MiMo v2.6 Flash attempts and the error body of the Qwen-family attempt do not exist in the folder (CC2-APP-14, CC2-APP-16).
7. The hidden scoring time is not recorded; the commit time of the final hidden report (2026-07-26T14:39 local) was used as the reference for "after the hidden scoring".
8. Process note: while searching the audit folder for the origin of the figure 117 I printed two lines of the revision-0 summary through a grep, before I had written my own verdict on the grader composition. The verdict CC2-LME-05 was derived from the raw judgment rows (and the .orig pre-adjudication files) and I did not use those lines. The revision-0 report was otherwise read only after the verdicts were formed.
9. No network, API or paid call was made. The only files written are in review_claimcheck2/ and a temporary export of the baseline commit in /tmp/cc2_base.

## Counts

Rows in CLAIM_CHECK2_REPORT.csv: 177

| Verdict | Count |
|---|---:|
| SUPPORTED | 137 |
| WEAKER_THAN_STATED | 30 |
| CONTRADICTED | 3 |
| UNVERIFIABLE | 7 |

## Findings that matter most

1. **Grader composition (CONTRADICTED, CC2-LME-05).** Before adjudication the 128 correct answers are 118 parsed model-judge verdicts, 8 deterministic guards and 2 substring fallbacks. The draft states 117, 9 and 2. The figure 9 is the post-adjudication guard count (post: 126, 9, 2 = 137), so the draft mixes pre- and post-adjudication counts. It was inherited from the revision-0 report, which I disagree with here.
2. **Reply parser of the substitute runs is undisclosed (WEAKER, CC2-D-04, CC2-MGP-46, CC2-ABS-11, CC2-DIS-09).** All 6,480 stored actions equal the output of an uncommitted working-tree parser (strict json-fence normalization, file time 2026-10-02T11:00:26Z, one minute before the Gemini medium run). With the parser of the baseline commit, 49 (low), 471 (medium) and 212 (high) replies are invalid; the cell A accuracy of Gemini medium would be 0.406 instead of 0.808 and that of Gemini high 0.478 instead of 0.961. The sign reversal for Gemini high and the 0.961 used in the discussion depend on this. GLM and gpt-oss replies parse identically under both parsers.
3. **Mean indexed position (CONTRADICTED, CC2-MGP-08).** Equality across actions holds in each public split, but 3.575 is the development split only (train 3.600, pooled public 3.5875).
4. **Builder-reported pool structure (UNVERIFIABLE, CC2-MGP-09).** The only tracked report says 120 of 120 triples, i.e. the 40 public components; neither the builder source nor the verifier contains a pool check.
5. **Labelling agreement (WEAKER, CC2-MGP-16).** Label agreement is 1.0, but annotator evidence selections never matched exactly (0 of 900; annotator B added the baseline turn T01 to every item).
6. **DeepSeek attempt (CONTRADICTED, CC2-APP-15).** Three items, not four, were retried to 4,096 tokens, and one of the eight records is an answer.
7. **Hidden run resume not disclosed (WEAKER, CC2-MGP-21).** The hidden generation was interrupted after 432 of 540 predictions and resumed.
8. **What is verified.** Every number in Tables models-acc and models-con reproduces from raw rows (CC2-A-01, CC2-A-02); the hidden confusion matrix, the 12,654-row replay (0 mismatches, deviation 0.0), the 34 tests, the 19 of 19 probe acceptances, the run windows, repeats, seed flags and token limits of Appendix E, and the b4-only coverage of the derived manifest all agree with the draft.

## All non-SUPPORTED items with minimal fixes

| id | verdict | location | claim (shortened) | fix |
|---|---|---|---|---|
| CC2-ABS-01 | WEAKER_THAN_STATED | 00_abstract.tex:sentence 2 | ASK ... records each decision together with the features, thresholds and identifiers needed to recompute it. | Write: "the features, scores, thresholds and identifiers needed to recompute the action (the score weights are code defaults and are not in the row)". |
| CC2-ABS-02 | WEAKER_THAN_STATED | 00_abstract.tex:sentence 3 (first clause) | The reference specification was written after the evaluations reported here | Write: "was first committed after the LongMemEval run and after the MGP-6 hidden evaluation". |
| CC2-ABS-04 | WEAKER_THAN_STATED | 00_abstract.tex:sentence 4 | We report three streams of evidence and keep them separate. | Say "four streams" and name the decomposition as an additional, separate public-development stream, or add it to Table 1. |
| CC2-ABS-05 | WEAKER_THAN_STATED | 00_abstract.tex:sentence 5 | MGP-6 v4.3 is a controlled synthetic diagnostic in which the three actions are distinguished by which two of six pooled sentences the dialog | Add "(verified on the 40 public components)". |
| CC2-ABS-11 | WEAKER_THAN_STATED | 00_abstract.tex:sentence 9 | A decomposition on the public development split with five substitute configurations of three models shows that the contributions of evidence | Disclose the parser per configuration (CC2-D-04) and write "differences in accuracy associated with ... differ among configurations, including in sign for one configuration". |
| CC2-ABS-13 | UNVERIFIABLE | 00_abstract.tex:sentence 10 | Each element of ASK has prior or concurrent precedent, and we make no priority claim. | Name the elements and cite Section 2: "write gating, abstention, supersession with lineage, event records and replay each have precedents we identified (Section 2)". |
| CC2-INT-02 | WEAKER_THAN_STATED | 01_introduction.tex:para 1, sentence 5 | Several widely used evaluations of long-term memory report the accuracy of final answers, which mixes the quality of the write decision with | Add \citep{arxiv_2410_10813,arxiv_2606_17328} and replace "widely used" by "common". |
| CC2-INT-04 | WEAKER_THAN_STATED | 01_introduction.tex:para 2, sentence 2 | KEEP preserves the stored state, SUPERSEDE replaces a stored item with a successor while retaining the predecessor and a link to it, and ABS | Write "KEEP is intended to preserve the stored state (in the evaluated runtime it inserts the candidate as a new record, Section 3)". |
| CC2-INT-07 | WEAKER_THAN_STATED | 01_introduction.tex:contribution 2 | MGP-6 v4.3 keeps the evidence sentences fixed within a component and varies which sentences the dialogue indexes to the target slot (the num | Add "(verified on the 40 public components)". |
| CC2-INT-11 | UNVERIFIABLE | 01_introduction.tex:precedent sentence | Each element of ASK has prior or concurrent precedent (Section 2); the contribution is the specification, the diagnostic and the evidence re | Same as CC2-ABS-13. |
| CC2-MGP-02 | UNVERIFIABLE | 04_mgp6.tex:line 4 | 30 for each of six scenario families | Verify against the v2 builder or drop the family count. |
| CC2-MGP-08 | CONTRADICTED | 04_mgp6.tex:line 7 | in our recomputation on the public components the mean indexed position is the same for the three actions (3.575) | Write "the mean indexed position is identical for the three actions within each public split (3.600 in train, 3.575 in development, 3.5875 pooled)". |
| CC2-MGP-09 | UNVERIFIABLE | 04_mgp6.tex:line 7 | This pool structure is reported by the builder for all 100 components and we recomputed it on the 40 public components only. | Say "the tracked analysis reports it for the 40 public components (120 triples); we have no verified report for the 60 hidden components". |
| CC2-MGP-14 | UNVERIFIABLE | 04_mgp6.tex:line 9 | per-probe accuracies are in the release and are not reproduced here | Say where they are, or report the maximum probe accuracy. |
| CC2-MGP-16 | WEAKER_THAN_STATED | 04_mgp6.tex:line 11 | Two annotation packets covered all 900 items and agreed exactly (raw agreement 1.0, kappa 1.0, 300 ambiguity flags raised). | Write "agreed on all 900 action labels (raw agreement 1.0, kappa 1.0); evidence selections differed in all 900 items by one baseline turn". |
| CC2-MGP-21 | WEAKER_THAN_STATED | 04_mgp6.tex:line 15 | One complete hidden prediction generation was authorized for the frozen controls. The hidden split has been consumed; we know of no rerun an | Add one sentence: "The run was interrupted once after 432 predictions and resumed under the same frozen controls". |
| CC2-MGP-41 | WEAKER_THAN_STATED | 04_mgp6.tex:line 62 | The prompt factor is itself a bundle (action definitions, resolvability criteria, abstention criteria and an output constraint), and the rep | List the evidence-scope instruction in the bundle and state that the SYSTEM label differs between cells D and E and their prompt-matched partners. |
| CC2-MGP-46 | WEAKER_THAN_STATED | 04_mgp6.tex:line 64 | For Gemini at high reasoning ... the ordering reversed | Report both readings (tolerant and baseline parser) for the three Gemini settings, or state that the sign reversal depends on reply formatting. |
| CC2-MGP-51 | WEAKER_THAN_STATED | 04_mgp6.tex:line 66 | These intervals are item-level bootstrap intervals (10,000 resamples, seed 0) that ignore the grouping of items into components, so they are | Add "numpy default_rng(0), shared resample indices". |
| CC2-LME-05 | CONTRADICTED | 05_lme.tex:line 7 | The grader scored 128 of 180 answers as correct (0.711): 117 by parsed verdicts of the model judge, 9 by deterministic guards applied before | Write "118 by parsed verdicts of the model judge, 8 by deterministic guards applied before the judge (40 answers were never sent to the judge, 32 of them scored incorrect) and 2 by a substring fallback". Optionally add the post-adjudication split 126/9/2. |
| CC2-LME-16 | WEAKER_THAN_STATED | 05_lme.tex:line 38 | (the earlier judge was routed to a free tier of the same model with a fallback) | Write "(the earlier manifest names a free-tier primary judge with a fallback; its call logs record requests to the identifier without the ":free" suffix, routed to a dated revision)". |
| CC2-LME-19 | WEAKER_THAN_STATED | 05_lme.tex:line 38 | The check as recorded in the run directory returned false because of a stale launcher hash, and it covered the controller only; the five-sys | Write "we found no record of the five-system check". |
| CC2-LME-20 | WEAKER_THAN_STATED | 05_lme.tex:line 38 | The run directory contains judgments for four baselines ... with 9, 80, 43 and 114 correct answers. [juxtaposed with the controller counts o | Keep the baseline counts in Appendix C only. |
| CC2-LME-24 | WEAKER_THAN_STATED | 05_lme.tex:line 43 | The scorecard modules are not among the files whose hashes the run manifest recorded, which is why the exact match is informative: it indica | Write "the released scorecard gives the same decisions and scores on all 12,654 logged feature vectors". |
| CC2-LME-26 | WEAKER_THAN_STATED | 05_lme.tex:line 45 | In the log, 88 rows repeat a (session, candidate identifier) pair, and 1,277 candidate texts receive more than one decision, mostly under di | Write "1,277 (session, candidate text, type) combinations receive more than one decision". |
| CC2-DIS-06 | WEAKER_THAN_STATED | 06_discussion.tex:line 7 | A high score therefore measures the ability to apply the decision criteria to the indexed evidence, and it does not measure the ability to f | Write "measures the model with its public-evidence guard on the indexed evidence". |
| CC2-DIS-08 | WEAKER_THAN_STATED | 06_discussion.tex:line 7 | The 2 x 2 decomposition ... shows that the split between routing and prompt, and even its sign, depends on the configuration, so it cannot b | Write "differs among the five configurations; for one of them the difference in sign depends on reply formatting". |
| CC2-DIS-09 | WEAKER_THAN_STATED | 06_discussion.tex:line 7 | In particular, on the development split a one-line prompt on the full payload reached 0.961 with one substitute configuration, so the hidden | Write "suggests, but does not show, that the hidden accuracy of 0.848 is not a ceiling for other models". |
| CC2-CON7-01 | WEAKER_THAN_STATED | 07_conclusion.tex:sentence 1 | We described an interface that names three decisions about a proposed memory write and records each decision with the information needed to  | Same as CC2-ABS-01. |
| CC2-APP-12 | WEAKER_THAN_STATED | 08_appendix.tex:App E table header | Model (gateway name) | Rename the column "Model and setting" or give the gateway identifiers. |
| CC2-APP-13 | WEAKER_THAN_STATED | 08_appendix.tex:App E text | Models were chosen by availability through a one-request test before any development accuracy was seen. | Write "the four later configurations were chosen by availability, after the Gemini low accuracies had been inspected". |
| CC2-APP-14 | UNVERIFIABLE | 08_appendix.tex:App E text | Qwen-family hosted model (the upstream provider reported the model as unavailable) | Say "returned HTTP 400" or keep as owner-reported. |
| CC2-APP-15 | CONTRADICTED | 08_appendix.tex:App E text | DeepSeek v4.1 Flash (on the same four items its hidden reasoning used all 1,024 and then all 4,096 allowed tokens and returned no answer, wi | Write "on three items its hidden reasoning used all 1,024 and then all 4,096 allowed tokens and returned no answer; one further item was answered at 1,024 tokens; 8 records were written". |
| CC2-APP-16 | UNVERIFIABLE | 08_appendix.tex:App E text | Kimi K2.5 (unavailable), MiMo v2.6 Flash (33.8 seconds for a one-line request, not run) | Mark as owner-reported. |
| CC2-D-04 | WEAKER_THAN_STATED | *.tex:line 62 and App E (omission) | using the repository's own builders and temperature 0 [no statement about how replies were parsed] | State per configuration which parser was used, that the baseline-commit parser rejects fenced replies, and give the tolerant-parser and strict-parser accuracies for the Gemini settings (or note that the tracked manuscript-model runs used the strict parser). |
| CC2-CON-01 | WEAKER_THAN_STATED | whole draft:abstract vs Section 1 vs Table 1 | three streams (abstract) / four evidence streams (Table 1) / decomposition not in either | Add the decomposition and the development comparison as rows of Table 1 with what they support. |
| CC2-CON-04 | WEAKER_THAN_STATED | whole draft:Section 5 line 38 and Appendix C | implied comparative LongMemEval result | Keep the counts in Appendix C only, with the disclaimer. |
| CC2-CON-05 | WEAKER_THAN_STATED | whole draft:Section 4 line 15 and line 64 | two different 0.961 values | Add a clause that the two values are unrelated (different models, prompts and procedures). |
| CC2-CON-06 | WEAKER_THAN_STATED | whole draft:Section 1 vs Section 4 | "fixed within a component" versus "(component, length) triple" | Use "within a component" in both, with the public-components qualifier. |
| CC2-CON-08 | WEAKER_THAN_STATED | whole draft:evidence streams mixed in one sentence | sentences joining MGP-6 v4.3 hidden, MGP-6 v2, V12 downstream and substitute-model development results | See CC2-DIS-09. |

## Part A: recomputation discrepancy table

Method: latest row per (item, cell, repeat); accuracies as the mean over repeats of per-repeat accuracy; guarded B through apply_live_controller_guard of the baseline commit; contrasts on per-item means over repeats; bootstrap numpy default_rng(0), integers(0,180,(10000,180)), percentile 2.5 and 97.5, one index matrix shared by all contrasts. Prompt SHA-256 of every row equals the prompt rebuilt with the baseline-commit builders (0 mismatches in 6,480 rows). Values in claimcheck2_recomputed.json.

| Item in draft | Draft | Recomputed | Verdict |
|---|---|---|---|
| Table models-acc, 25 cells | printed at 3 dp | max abs difference 0.0000 | no discrepancy |
| Table models-con, 20 contrasts | printed at 3 dp | all equal at 3 dp | no discrepancy |
| Table models-con, 40 interval endpoints | printed at 2 dp | all equal at 2 dp (default_rng(0)); 8 endpoints move by 0.01 with RandomState(0) | rounding and generator only |
| B minus A range | -0.11 to +0.40 | -0.1111 to +0.4028 | no discrepancy |
| gpt-oss cell A, repeat 1 SUPERSEDE predictions | 177 of 180 | 177 (KEEP 1, ABSTAIN 2); repeat 2: 174 | no discrepancy |
| Gemini high live cells ABSTAIN | 84 and 81 vs 60 gold | 84 (E) and 81 (B) vs 60 | no discrepancy |
| Appendix E repeats | 2, 2, 1, 2, 2 | 2, 2, 1, 2, 2 | no discrepancy |
| Appendix E windows (UTC) | low 1 Oct 16:59-17:16; medium 11:01-11:44; high 11:50-12:39; GLM 09:58-10:47; gpt-oss 09:37-09:55 | from utc fields: 16:59:37-17:16:31; 11:01:25-11:44:30; 11:50:02-12:39:26; 09:58:54-10:47:00; 09:37:04-09:55:28 | no discrepancy |
| Appendix E seed flags and max new tokens | no/4301/4301/no/4301; 512/4096 | summary.json sent_seed false/true/true/false/true (low: runner has no seed field); max_tokens 512 (low), 4096 (others) | no discrepancy |
| Parser used (not stated in draft) | not stated | baseline-commit parser rejects 49/471/212 stored replies for Gemini low/medium/high | omission (CC2-D-04) |
| Interaction (not in draft) | "each factor's gain is smaller" for GLM and gpt-oss | (B-D)-(E-A) = -0.217 [-0.294,-0.142] and -0.153 [-0.239,-0.061] | supports the wording (clustering ignored) |

## Part C: internal consistency

- CC2-CON-01 (WEAKER_THAN_STATED): three streams (abstract) / four evidence streams (Table 1) / decomposition not in either Abstract sentence 4 says three streams; Section 1 Table 1 has four rows; the decomposition (public development, substitute models) and the development-split comparison of the manuscript model (Table dev) are evidence blocks that Table 1 omits.
- CC2-CON-02 (SUPPORTED): 0.848, 540, 60 components; 128, 137, nine; 12,654; 19 probes; 34 tests; 17 files (7 + 10); five configurations of three models Abstract, Section 1, Section 4, Section 5, Section 6, Section 7, Appendices and tables agree on every repeated number; rounding differences only (0.8481 versus 0.848, 0.8479 versus 0.848).
- CC2-CON-03 (SUPPORTED): every table, figure and section reference 22 labels, 0 undefined references (tab:roles, tab:hidden, tab:dev, tab:models-acc, tab:models-con, fig:models, tab:lme, fig:lme, tab:neighbors, app:*), figure files exist, 35 citation keys all present in references.bib. Unused labels: sec:intro, sec:mgp6-protocol, sec:discussion, sec:conclusion (harmless).
- CC2-CON-04 (WEAKER_THAN_STATED): implied comparative LongMemEval result No comparative claim is made, and each mention is disclaimed. The baseline counts (9, 80, 43, 114) are printed in the body next to the controller counts, which lets a reader form the comparison the paper rejects. The abstract and conclusion contain no comparative LongMemEval statement.
- CC2-CON-05 (WEAKER_THAN_STATED): two different 0.961 values The successor configuration (qwen3.5-9b, guard composed) scored 0.9611 on development (173/180) and the Gemini high one-line cell A also scored 0.9611 (173/180); the coincidence is noted in PHASE16 16.5 item 7 but not in the draft, and both appear in the same section and again in Section 6.
- CC2-CON-06 (WEAKER_THAN_STATED): "fixed within a component" versus "(component, length) triple" The public data support the stronger statement (one pool per component across lengths, 40 of 40) so the two are not contradictory, but the introduction and Section 4 should use one formulation.
- CC2-CON-07 (SUPPORTED): em dashes, en dashes, and the words first, unique, novel, solves, safe, demonstrates, state of the art No em or en dash in main.tex, sections or tables. "first"/"First" occur only as ordinals or in "first committed"; "demonstration" occurs once in the future-work list; "safe", "novel", "unique", "solves", "demonstrates" do not occur. Mild causal vocabulary: "contributions" (abstract), "depends on the configuration" (Section 4, 6), "A high score therefore measures" (Section 6): see CC2-ABS-11, CC2-DIS-06, CC2-DIS-08.
- CC2-CON-08 (WEAKER_THAN_STATED): sentences joining MGP-6 v4.3 hidden, MGP-6 v2, V12 downstream and substitute-model development results One sentence joins streams: Section 6 line 7 uses a substitute-model development result to qualify the hidden accuracy (CC2-DIS-09). Abstract sentences 5 to 9 keep the streams in separate sentences.

Abstract and conclusion versus the body: the abstract and Section 7 repeat the claim that each decision is recorded with what is needed to recompute it (CC2-ABS-01, CC2-CON7-01), which the body supports only for the action; the abstract says the specification was written after "the evaluations reported here", which the decomposition runs of October contradict (CC2-ABS-02). The conclusion omits the decomposition, which is acceptable. Neither states a comparative LongMemEval result.

## Cross-check against the revision-0 report (read after the verdicts above)

- Resolved from revision 0: CC-044/CC-161 (validator row now reads correctly), CC-113/CC-142/CC-158 (seed wording now "request seed 0 sent"), CC-160 (B1 row), CC-152 (b4-only coverage stated), CC-070 (successor disclosed), CC-136 (largest share), CC-126 (homogeneity wording).
- Disagreement: revision 0 reported "9 of 40 guarded answers correct" and "117 parsed" for the 128 raw correct (CC-110). The raw rows give 8 and 118 before adjudication; 9 is the post-adjudication value. Revision 1 copied the revision-0 composition.
- Persisting in changed form: CC-056 (hidden-component pool statement) is now worded as "reported by the builder for all 100 components", which I could not verify (CC2-MGP-09). CC-063 (agreement wording) was softened to "consistent with" and is acceptable; the label versus evidence agreement point (CC2-MGP-16) is new.
- Additional hash source: the SHA-256 of the b1 to b3 judgments are also recorded in artifacts/analysis/lme_v12_adjacent_mcnemar.json (revision 0, CC-152); the appendix could cite it next to the byte-identity check.
- New in revision 1 and not covered by revision 0: the parser dependence, the mean-indexed-position value, the DeepSeek record count, the Appendix E model-selection sentence, the hidden-run resume, the label-agreement versus evidence-agreement distinction.

## Files

- CLAIM_CHECK2_REPORT.csv: one row per checked statement (id, file, location, claim, verdict, evidence, fix).
- claimcheck2_recompute.py and claimcheck2_recomputed.json: Part A recomputation and the Part B numerics (aggregates only).
- claimcheck2_validator_probes_rerun.py and .json: rerun of the Phase 6 probes on the exported baseline commit (19 of 19 accepted).
- build_claimcheck2_report.py: builds the CSV and this summary from the adjudicated rows.
