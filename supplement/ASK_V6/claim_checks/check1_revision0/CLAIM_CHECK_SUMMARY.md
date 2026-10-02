# Claim check summary

Independent claim check of the arXiv draft (main.tex and sections 00, 01, 03 to 08; closing paragraph of section 02 only). Report only; no draft file was edited. Evidence was read from the tracked repository at baseline commit f6bf66e, the audit record, and the owner backup of the V12 run directory (read only). Benchmark text was never printed, copied or saved: only counts, booleans, hashes and field lengths were computed.

## Declared reductions and process notes

- Section 02 was checked only for its closing "Scope of the comparison" paragraph and the line above it, as instructed. Table cells, citations and the bibliography (other than the LongMemEval entry) were not checked.
- The hidden MGP-6 split, its gold labels and its model-facing inputs are private and were not opened. Hidden-split structure claims (pool sharing, partition, no gold in inputs) are therefore UNVERIFIABLE here; public train and dev were recomputed instead (40 of 100 components).
- The 950 MB LongMemEval slice file, answers, predictions and judge rationales were not opened for content. Question types come from the judgments competency field; abstention questions are identified by the identifier suffix; adjudication notes were measured by length only.
- Figures were checked by viewing the PNG renderings against Tables 3 and 4, not by extracting plotted data from the PDF.
- The full repository test suite was not run. The five test files named in the Phase 6 record were run with bytecode and cache writing disabled (34 passed); git status was unchanged afterwards.
- Git reachability of the 17 recovered blobs was checked with read-only commands on the backup repository (rev-list over all refs).
- The finding that V12 guard rules were iterated on slice questions rests on directory names and set membership of identifiers only (provisional, inference from structure).
- No paid API, web search or network call was made.
- Process note: early in the work I wrote a scratch copy of three draft sections into the draft folder by mistake (draft_rest_tmp.txt). It was a copy, no draft file was altered, and it was moved to the Trash with the owner approval prompt.

## Counts

Rows in CLAIM_CHECK_REPORT.csv: 171

| Verdict | Count |
|---|---:|
| SUPPORTED | 127 |
| WEAKER_THAN_STATED | 27 |
| CONTRADICTED | 7 |
| UNVERIFIABLE | 10 |

| Category | SUPPORTED | WEAKER_THAN_STATED | CONTRADICTED | UNVERIFIABLE |
|---|---:|---:|---:|---:|
| CAUSAL | 1 | 4 | 1 | 1 |
| CONSISTENCY | 3 | 2 | 0 | 0 |
| FACT | 62 | 18 | 5 | 9 |
| NOVELTY | 2 | 0 | 0 | 0 |
| NUMBER | 56 | 1 | 1 | 0 |
| ROLE_MIXING | 1 | 2 | 0 | 0 |
| WORDING | 2 | 0 | 0 | 0 |

## Highest-impact findings (all in the lists below)

1. The statement that the generation seed was not set is contradicted in three places (Section 5 results, Discussion limitations, Appendix R6). The answer records, the homogeneity report, the run matrix and the evaluated code all show a request seed of 0.
2. "The judge scored 128 of 180" mixes three scoring paths: 117 parsed model-judge verdicts, 9 correct verdicts from deterministic pre-judge guards (40 answers were never sent to the judge), and 2 substring-fallback verdicts after unparseable judge output.
3. The homogeneity check recorded as false was a controller-only check that failed on a stale launcher hash. The draft attributes the failure to baseline heterogeneity, which the audit found separately.
4. Discussion says most hidden errors are gold-ABSTAIN items committed; the share is 38 of 82 (46%).
5. The abstract's "development gain" is the +0.13 gain of the substitute model, not the +0.505 gain in Table 2; the full-payload by live-prompt cell uses a prompt that describes a routed view the model does not receive.
6. "Differ only in which two of six sentences are indexed" is not supported: the numbered order of the six sentences also differs between the three actions in all 60 public dev triples.
7. The 64-zero configuration identity is not one of the 19 validator probes, and the Appendix claim row "The protocol validates conforming states" has a basis that points the other way (the four builder controls were accepted).
8. Table 2 reports the later complete development rerun (live controller 0.844); the selection run recorded in the repository scored 0.8556, and several baselines differ between the two runs. The draft does not say which run it reports.

## CONTRADICTED

- CC-044 | sections/03_interface.tex | line 32 | FACT | claim: "and a configuration identity consisting of 64 zeros" | The 64-zero identity is not one of the 19 validator probes and was accepted at object construction, not by ASKInvariantValidator.validate. Fix: Move it to the next sentence as a separate observation about the configuration identity.
- CC-113 | sections/05_lme.tex | line 7 | FACT | claim: "the answer model is a hosted service whose generation seed was not set" | A request seed of 0 was configured and sent. Whether the hosted provider honors it is unknown. The audit record "seed null" predates the raw-evidence phase. Fix: Write "a request seed of 0 was sent, but provider-side determinism is not established".
- CC-126 | sections/05_lme.tex | line 38 | CAUSAL | claim: "The homogeneity check required by the plan ... therefore failed" | The recorded false is caused by a stale launcher hash in a controller-only check. Baseline heterogeneity was found by the audit, not by this check, and the plan-required five-system check was never run. Fix: Say that the check as recorded returned false for a stale-hash reason, and that the baseline heterogeneity was identified separately.
- CC-136 | sections/06_discussion.tex | line 3 | NUMBER | claim: "with most errors being gold-ABSTAIN items that were committed" | The largest share is 46%, not a majority. Fix: Write "the largest share of errors (38 of 82)".
- CC-142 | sections/06_discussion.tex | line 9 | FACT | claim: "the generation seed was unset" | Second location of the seed statement. Fix: See Section 5 fix.
- CC-158 | sections/08_appendix.tex | Table B, R6 | FACT | claim: "Not established: hosted model, generation seed not set" | Third location of the seed statement; the "not established" status holds, the reason does not. Fix: Write "hosted model; request seed 0 sent; provider determinism not established".
- CC-161 | sections/08_appendix.tex | Table D, row 7 | FACT | claim: "The protocol validates conforming states - Not supported - 19 of 19 tampering probes accepted" | Accepting tampered states shows the validator does not reject non-conforming states. It does not show that conforming states are rejected; the controls were accepted. The claim and its basis do not match. Fix: Rewrite as "The validator rejects non-conforming states - Not supported - 19 of 19 tampering probes accepted".

## WEAKER_THAN_STATED

- CC-005 | sections/00_abstract.tex | line 2, sentence 5 | FACT | claim: "three actions differ only in which two of six pooled sentences the dialogue indexes" | The pool and the partition of indexed pairs hold, but the numbered order of the six sentences is also permuted between the three actions. "Only" is not supported as stated; the order change is balanced (mean indexed position 3.575 for each action) but is an additional difference. Fix: Say the actions differ in the indexed pair and in the numbering of the pooled sentences, or drop "only".
- CC-009 | sections/00_abstract.tex | line 2, sentence 9 | ROLE_MIXING | claim: "associates most of the development gain with the decision prompt rather than with evidence routing" | "The development gain" reads as the qwen gain in Table 2. The decomposition accounts for a +0.131 gain on a different model that starts at 0.76. The qwen gain is not decomposed. Fix: Write "most of the +0.13 gain observed with the substitute model", and state that the qwen gain was not decomposed.
- CC-017 | sections/01_introduction.tex | item 2, line 10 | FACT | claim: "holds the surface form of the evidence fixed within a component and varies only which sentences the dialogue indexes" | Third location of the "only" statement; the sentence texts are fixed, the sentence order is not. Fix: Same fix as the abstract row.
- CC-018 | sections/01_introduction.tex | item 3, line 11 | FACT | claim: "128 correct before and 137 correct after nine manual adjudications of the judge's output" | Eight of the nine overrides changed a model-judge verdict. One changed a verdict from a deterministic pre-judge guard (judge_was_called false). Fix: Write "nine manual adjudications of the grader output" or state 8 judge verdicts and 1 guard verdict.
- CC-022 | sections/01_introduction.tex | Table 1 row 3 | FACT | claim: "Answer correctness judged by a model" | 40 of 180 verdicts come from deterministic pre-judge guards and 2 judge outputs were unparseable and scored by a substring fallback. Fix: Write "judged by a model with deterministic guards for 40 answers and a substring fallback for 2".
- CC-029 | sections/03_interface.tex | line 15 | FACT | claim: "Two scores, S_rev and S_abs, are computed from these features with configured weights" | Only S_rev is weighted. Fix: Say "S_rev uses configured weights; S_abs is unweighted".
- CC-042 | sections/03_interface.tex | line 32 | NUMBER | claim: "The test suite of 34 tests passes." | 34 is a five-file subset that includes memory-operation, temporal and supersede tests, not the repository test suite (postfinal_successor/DEV_CANDIDATE_CONFIG.json records 547 passed, 11 skipped for the full suite). Fix: Write "34 tests in the five files that cover the protocol and the memory operations, 10 of them specific to the protocol".
- CC-055 | sections/04_mgp6.tex | line 7 | FACT | claim: "the three actions differ only in which two of the six sentences the dialogue indexes" | Second location of the "only" statement. Fix: Same fix as the abstract row.
- CC-057 | sections/04_mgp6.tex | line 7 | FACT | claim: "The model-facing record contains an opaque identifier, the stored memory and the dialogue, and no field that names a design target or component." | The model-facing record has a fourth field, evaluation_query. Fix: Add the evaluation query to the list.
- CC-059 | sections/04_mgp6.tex | line 9 | FACT | claim: "word and character TF-IDF classifiers on 12 restricted text views" | Character n-gram probes cover 2 of the 12 views. Fix: Say "word TF-IDF on 12 views and character TF-IDF on 2 views".
- CC-060 | sections/04_mgp6.tex | line 9 | FACT | claim: "These checks show that the tested lexical probes did not recover the action" | Ceilings reach 0.65, nearly twice the 0.333 chance level, so passing a ceiling does not mean the action was not partly recovered. The probe accuracies are not available to confirm. Fix: Say "stayed at or below preset ceilings (0.40 to 0.65)" and report the per-probe accuracies.
- CC-063 | sections/04_mgp6.tex | line 11 | CAUSAL | claim: "perfect agreement shows that the manual is followable and that the items instantiate it" | Agreement between two packets whose annotators are not authenticated, and which may not be independent, does not by itself show that a second person can follow the manual. The next sentence concedes the identity gap. Fix: Replace "shows" by "is consistent with".
- CC-065 | sections/04_mgp6.tex | line 15 | FACT | claim: "live controller gives a language model the two messages that the public index points to, together with a prompt that states decision criteria" | The description omits the stored memory, the extracted requested value and the query that the model also receives. Fix: List the full view contents.
- CC-086 | sections/04_mgp6.tex | line 38 | FACT | claim: "the four component ablations receive the full payload with their own prompts" | Three of the four receive the full payload; no-provenance receives a stripped view. Fix: Write "three receive the full payload and no-provenance receives the dialogue without provenance".
- CC-095 | sections/04_mgp6.tex | line 62 | ROLE_MIXING | claim: "With either evidence view, the live prompt was associated with a gain" | The full-payload by live-prompt cell is a mismatched condition (prompt text describes a view the model does not receive). The report labels it a diagnostic cell; the draft does not. Fix: State that the full-payload by live-prompt cell uses a prompt whose text assumes the routed view.
- CC-096 | sections/04_mgp6.tex | line 62 | CAUSAL | claim: "The effects look approximately additive." | "Effects" is causal wording for a four-cell comparison on one model; additivity was not tested. Fix: Write "the differences are similar across levels of the other factor".
- CC-106 | sections/05_lme.tex | line 4 | FACT | claim: "The slice had been used to tune the preceding controller version" | The plan says V12 was selected after inspecting partial V11 outcomes on this slice. The backup also shows V12 guard iterations on slice questions on 2026-07-18, so tuning reaches V12 itself. This is a provisional inference from directory structure; the content was not read. Fix: Say "used to select and tune the V11 and V12 controller versions".
- CC-110 | sections/05_lme.tex | line 7 | FACT | claim: "The judge scored 128 of 180 answers as correct" | Of the 128, 9 come from deterministic pre-judge guards, 2 from a substring fallback and 117 from parsed model-judge verdicts. Fix: State the three scoring paths and the counts per path.
- CC-119 | sections/05_lme.tex | line 29 | CAUSAL | claim: "concentration suggests that the model judge and the human reader disagree most where the reference is a preference description" | The nine cases were selected by a script; coverage of the other 43 failures is not recorded. Concentration may reflect where failures and reviewer attention were concentrated. Fix: Say that seven of nine reviewed cases were in that type, and that review coverage of other failures is not documented.
- CC-137 | sections/06_discussion.tex | line 3 | FACT | claim: "The LongMemEval run shows that the controller answered 128 of 180 questions correctly under the judge" | Same attribution issue as Section 5.
- CC-138 | sections/06_discussion.tex | line 3 | CAUSAL | claim: "one frozen configuration separates the three actions" | Discriminative claim stated without a baseline in the same conditions; the paper itself says no matched comparison exists. Fix: Use "classifies the three actions with accuracy 0.848".
- CC-143 | sections/06_discussion.tex | line 9 | FACT | claim: "the adjudication was applied to one system" | Manual adjudication was applied to one system, but three baseline verdicts were overridden by an undocumented process. Fix: Add "and three baseline verdicts carry undocumented overrides".
- CC-144 | sections/06_discussion.tex | line 9 | FACT | claim: "the run was executed once" | The final configuration was run to completion once after two resumes, but not the first run on this slice. Fix: Say "the final configuration was run once (after two resumes)".
- CC-151 | sections/07_conclusion.tex | line 3 | FACT | claim: "a validator and a persistence layer that are incomplete" | "Incomplete persistence layer" implies a partial layer; none exists. Fix: Write "a validator that accepts non-conforming states and no persistence layer".
- CC-152 | sections/08_appendix.tex | App. A line 4 | FACT | claim: "judgments and report of the controller, its action log, and the judgments of the four baselines match the SHA-256 values in the repository derived manifest" | The derived manifest covers only b4 among the baselines. Fix: Name both files.
- CC-160 | sections/08_appendix.tex | Table C, B1 row | CONSISTENCY | claim: "B1 no memory: 9, earlier run" | The table flags the B4 overrides but not the B1 override, while the text (Section 5) lists three. Fix: Add "(10 before one undocumented override)" to the B1 row.
- CC-167 | multiple files | cross-file | CONSISTENCY | claim: "dev live-controller accuracy 0.844 in Table 2 versus the selected development candidate" | The repository holds two development results for the live controller and different values for several baselines (for example zero-shot 0.3333 versus 0.3389, B3 0.3389 versus 0.3278, no-abstention macro-F1 0.2398 versus 0.2465). The draft reports only the rerun values and calls them "tracked results" without naming the run. Fix: Name the source run in the Table 2 caption and state the selection-run value.

## UNVERIFIABLE

- CC-011 | sections/01_introduction.tex | line 3 | FACT | claim: "Most evaluations of long-term memory report the accuracy of final answers" | Generalization over the literature without support. Fix: Cite the benchmarks surveyed or soften to "Several".
- CC-012 | sections/01_introduction.tex | line 3 | CAUSAL | claim: "replacing a value on weak evidence destroys information, and refusing a well-supported update leaves the memory stale" | Stated as fact about failure costs. It does not hold for ASK SUPERSEDE, which retains the predecessor, so the sentence applies only to replace-in-place memories. Fix: Qualify as "for memories that overwrite in place" and add a citation or mark as motivation.
- CC-026 | sections/03_interface.tex | line 9 | FACT | claim: "predecessor is retained, marked as superseded, and linked to the successor by an identifier and a relation row, within one database transaction" | The memory module used in the V12 run is not among the 17 hashed files, so the evaluated version is not identified; the released code supports the sentence. Fix: Attribute to the released code or hash the evaluated module.
- CC-036 | sections/03_interface.tex | line 26 | FACT | claim: "with a flush to disk for every row" | The writer module is not among the 17 hashed files and its history before the 2026-07-25 rename commit was not traced. Fix: Hash the evaluated writer or attribute the statement to the released code.
- CC-052 | sections/04_mgp6.tex | line 7 | FACT | claim: "Items are human-authored and template-guided." | Only the dataset card asserts authorship; no independent provenance. Annotator identity is flagged in the audit record (CS-16). Fix: Attribute to the dataset card or add authorship provenance.
- CC-056 | sections/04_mgp6.tex | line 7 | FACT | claim: "the same pool and partition for the 60 hidden components" | The statement is made for all 100 components; only the 40 public components were verified here. Fix: Scope the sentence to what was checked, or cite the builder verification.
- CC-070 | sections/04_mgp6.tex | line 15 | FACT | claim: "The hidden split has been consumed, and we have not tuned against it or rerun it." | No rerun is recorded. A post-final successor configuration (development accuracy 0.95 and 0.9611, tracked in the analysis JSON) was designed after the hidden aggregate was known; it is dev-informed by its own README and is not mentioned in the draft. The negative claim cannot be verified from files. Fix: Disclose the successor in one sentence and state that it was not run on the hidden split.
- CC-072 | sections/04_mgp6.tex | line 15 | FACT | claim: "The hidden inputs given to the model contained no gold labels" | Record-based; hidden inputs are private and were not inspected.
- CC-117 | sections/05_lme.tex | line 29 | FACT | claim: "We did not review the failures of any other system by the same criteria" | Negative process claim; absence of a record is not proof. Three undocumented baseline overrides exist.
- CC-165 | sections/02_related_work.tex | line 45 | FACT | claim: "whose search record is released" | Depends on publication of SEARCH_LOG.csv. Fix: Cite the location of the released log when known.

## What was not checked, and why

- Correctness of feature extraction, relation classification, memory state or answers in the V12 run: no state was persisted, and the draft does not claim it (replay levels R2 to R7).
- Whether a hosted provider honors a request seed: not observable from files.
- Annotator independence and authorship of MGP-6 items: no independent provenance exists in the evidence set (audit finding CS-16).
- Existence of a released search log and of the figures in the final PDF: not part of the evidence set.
- Related-work classifications of individual comparators and their citations: out of scope by instruction.
- Whether the post-final successor configuration influenced design choices through knowledge of hidden aggregates: not decidable from files; it is listed as an undisclosed item.
- LaTeX compilation, reference resolution and typography: not checked.

## Files

- CLAIM_CHECK_REPORT.csv: one row per checked claim (columns as specified).
- claimcheck_recompute.py and claimcheck_recomputed.json: aggregate-only recomputation of the numbers used (no benchmark text).
- build_claimcheck_report.py: generates the CSV and this summary from the row definitions.
