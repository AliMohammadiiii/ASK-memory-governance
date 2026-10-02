# Claim Check 4 summary (frozen revision 4)

Reviewer role: independent claim checker (Claim Check 4), fresh context. Report file: CLAIM_CHECK4_REPORT.csv (189 rows). No manuscript or repository file was modified; scratch work is under /tmp.

## Items I could not fully check (declared first)

- Compiled layout of main_v4.pdf: page images were requested but no rendered content was returned to me and no PDF text tool exists in the sandbox. Overfull boxes, "??" references and rendering problems are NOT verified. Source-level checks (labels, citations, bbl) were done.
- Section 2 characterisations of other works (about 25 statements) were not verified from full text (no network). Only bibliography key/identifier consistency, Table 2 cells against the derivation file, the selection rule of the twelve neighbours and search-log counts were checked.
- MGP-6 pool structure (mean indexed positions 3.600/3.575/3.5875, 120 triples), shortcut-probe ceilings, v2 counts, hidden bootstrap accuracy interval, the guard count 36 of 202, the hidden-run interruption at 432 of 540 and the successor dev accuracies were not recomputed (private or unavailable data, or no accessible record).
- Table 4 (tracked development results, 0.844 etc.) could not be recomputed: I located only the earlier July development run (live controller 0.8556 / macro-F1 0.8566, matching the caption); the complete rerun directory was not found by me.
- Sentences changed after Claim Check 3 were identified by topic and keyword against the claim/location columns of the CC3 report (a fuzzy token-overlap pass produced 130 low-overlap sentences, too noisy to list), not by an exact diff; coverage of all changed sentences is therefore best-effort. All manuscript sentences were nevertheless read and the 189 rows cover every section, table and caption.
- Owner-provided provenance facts were not and cannot be authenticated; they are treated as metadata.

## 1. Hash verification

- main_v4.pdf SHA-256 = 14a6898f6c796e4e617595b304a9488a62d56be1f025ac593183570d21b6d597: MATCH.
- paper_v4_source.tar.gz SHA-256 = c0770c608c447046c6a932982fea3066000b1e83e5a074cbf7b31307767f740a: MATCH.
- Extracted to /tmp/cc4; every file in SHA256SUMS.txt verified (no mismatches). Archive also contains earlier review directories (review_claimcheck, review_claimcheck3); I did not read them.

## 2. Counts

Claims checked: **189**. SUPPORTED 141, WEAKER_THAN_CLAIM 14, CONTRADICTED 0, UNVERIFIABLE 34.

| Area | Supported | Weaker | Contradicted | Unverifiable | Total |
|---|---|---|---|---|---|
| ABSTRACT | 9 | 1 | 0 | 1 | 11 |
| AI_DISCLOSURE | 0 | 1 | 0 | 0 | 1 |
| APPENDIX | 8 | 1 | 0 | 4 | 13 |
| CONCLUSION | 6 | 0 | 0 | 0 | 6 |
| DISCUSSION | 8 | 0 | 0 | 1 | 9 |
| HIDDEN | 7 | 0 | 0 | 6 | 13 |
| INTERFACE | 15 | 1 | 0 | 0 | 16 |
| INTRO | 15 | 1 | 0 | 2 | 18 |
| LME | 20 | 2 | 0 | 0 | 22 |
| MGP6 | 9 | 1 | 0 | 9 | 19 |
| PARSER | 10 | 1 | 0 | 0 | 11 |
| PROVENANCE_OWNER | 0 | 3 | 0 | 0 | 3 |
| RELATED | 6 | 0 | 0 | 6 | 12 |
| RENDER | 0 | 0 | 0 | 1 | 1 |
| STYLE | 1 | 0 | 0 | 0 | 1 |
| SUBSTITUTE | 10 | 1 | 0 | 3 | 14 |
| TABLES | 4 | 0 | 0 | 1 | 5 |
| V12_LOG | 7 | 0 | 0 | 0 | 7 |
| V12_RESUME | 0 | 1 | 0 | 0 | 1 |
| XREF | 6 | 0 | 0 | 0 | 6 |

## 3. Every non-SUPPORTED item

### WEAKER_THAN_CLAIM (14), each with minimum defensible correction

- **CC4-007** (00_abstract.tex, 00_abstract.tex:2): ... and depend on how replies are parsed Correction: Write: "and, for the Gemini settings, on how replies are parsed".
- **CC4-023** (01_introduction.tex, 01_introduction.tex:12): 2x2 contrast with five substitute configurations found associated differences that differ among configurations and depend on how replies are parsed Correction: Qualify with "for the Gemini settings".
- **CC4-053** (03_interface.tex, 03_interface.tex:32): Corrected validator written as a patch against the baseline commit (supplement; not applied to the repository) Correction: Replace by: "supplied as a patch (ASK_supplement/validator/validator_fix.patch; also committed as 4fc32ca on a separate branch descending from the baseline commit; not part of the baseline commit)".
- **CC4-067** (04_mgp6.tex, 04_mgp6.tex:12): A third independent human served as adjudicator Correction: Add: "no label disagreement arose (adjudication count 0), so no label was adjudicated" and mark the adjudicator statement as owner-provided metadata not recorded in the release artifacts.
- **CC4-100** (04_mgp6.tex, 04_mgp6.tex:67): Intervals: paired bootstrap over the 20 components (nine items resampled together; 10,000 resamples, numpy default_rng(0), one set of indices shared by all contrasts; per-item results averaged over... Correction: Add: "components indexed in order of first appearance in the development file; indices drawn with rng.integers(0,20,(10000,20))".
- **CC4-116** (05_lme.tex, 05_lme.tex:4): The execution was interrupted and subsequently resumed under the same frozen controls rather than treated as a new experimental condition Correction: Write "per the run manifest (one control set recorded) and the owner, the execution was interrupted and resumed under the same frozen controls; per-invocation control hashes were not recorded".
- **CC4-123** (05_lme.tex, 05_lme.tex:7): The nine abstention questions were answered correctly in eight cases Correction: State that 8 of 9 is from the post-adjudication report.
- **CC4-128** (05_lme.tex, 05_lme.tex:29): The nine cases were adjudicated by an independent human reviewer Correction: Insert the qualifier used for MGP-6: "according to the study owner; the artifacts record neither reviewer identity nor date".
- **CC4-130** (05_lme.tex, 05_lme.tex:29): The same procedure was not applied to baselines; their three overrides came from a separate pass by an independent human reviewer; selection criteria and coverage not recorded Correction: Same qualifier as above; say the overrides carry no reviewer, date or tool record.
- **CC4-151** (06_discussion.tex, 06_discussion.tex:7): The two annotators were independent of the author, and a third independent human served as adjudicator; this independence is study metadata rather than something authenticated by the release artifacts Correction: Add one clause on adjudication count 0 and the recorded ids as owner-supplied labels.
- **CC4-153** (06_discussion.tex, 06_discussion.tex:9): Manual adjudication performed by an independent human reviewer but with an undocumented selection of cases; three baseline verdicts carry overrides by an independent human reviewer with undocumente... Correction: Attribute to the owner and say no reviewer id/date is recorded.
- **CC4-157** (06_discussion.tex, 06_discussion.tex:13): The reference-validator patch, the reanalyses of the substitute runs, the provenance reconciliation of the LongMemEval run, the claim checks and the drafting were carried out with an AI research as... Correction: Extend the list to every step the owner confirms (substitute runs and parser change, literature search and coding, figures/tables) and consider moving the statement to a front-matter or acknowledgments note.
- **CC4-171** (08_appendix.tex, 08_appendix.tex:32): Three overrides from an independent human reviewer whose selection criteria are not recorded Correction: Qualify as owner-provided.
- **CC4-179** (08_appendix.tex, 08_appendix.tex:113): Re-parsed 12 model-run directories of the complete development rerun and 12 of the earlier July development run (180 replies each): every reply parses under baseline-strict, none fenced Correction: Name the directories re-parsed, or restate as one set of 12 model-run directories.

### CONTRADICTED (0)

None.

### UNVERIFIABLE (34)

- CC4-002 (00_abstract.tex:2): MGP-6 v4.3: action depends on which two of six pooled sentences the dialogue indexes (verified on the 40 public components)
- CC4-012 (01_introduction.tex:3): Common evaluations report final-answer accuracy (LongMemEval) ; recent work argues final accuracy hides retrieval and evidence-use failures (MemTrace)
- CC4-018 (01_introduction.tex:10): MGP-6 v4.3 keeps evidence sentences fixed within a component and varies indexing; numbering also changes; verified on 40 public components
- CC4-030 (02_related_work.tex:5): A-MAC, SSGM, Persona, Memory-R1, MemGuard, CUPMEM/STALE, TARL, MemTX behaviours (admission, gate, rollback, ADD/UPDATE/DELETE/NOOP, SKIP, quarantine)
- CC4-031 (02_related_work.tex:5): Selective Memory, When Not to Write Memory, MemReader make write-time decisions with archive, needs-review and deferral outcomes
- CC4-032 (02_related_work.tex:7): Supersession and belief revision paragraph (Graph-native, TOKI, SodaMem, GPM, MemGuard verifier, ECHO, Governed Shared Memory, MemTX has no success...
- CC4-033 (02_related_work.tex:9): Transactional and event-sourced memory paragraph (MemTX, TARL, Quipu, The Log is the Agent, ESAA, MemLineage, SuperLocalMemory 4.0)
- CC4-034 (02_related_work.tex:11): MGP (HKUDS) specifies storage-independent and runtime-independent protocol, leaves write decision to the caller; GPM, TOKI, Eywa governance statements
- CC4-035 (02_related_work.tex:13): Evaluation resources paragraph (HaluMem, MemOps, MemTrace, TARL, MCB, CPB, MemTxn)
- CC4-058 (04_mgp6.tex:5): MGP-6 v2: 180 scenarios, 90 supersede, 66 abstain, 24 keep; lookup on conflict type reproduced held-out actions exactly
- CC4-060 (04_mgp6.tex:8): Three indexed pairs partition the pool; mean indexed position 3.600 train, 3.575 development, 3.5875 pooled; pool structure verified on 40 public c...
- CC4-062 (04_mgp6.tex:8): Items are described in the dataset card as human-authored and template-guided; no independent provenance for authorship
- CC4-063 (04_mgp6.tex:10): Shortcut probes (12 word TF-IDF views, 2 char views, punctuation, length, trees depth 1-5) stayed at or below preset ceilings; duplicate audit pass...
- CC4-066 (04_mgp6.tex:12): Packets were completed by two human annotators independent of the author
- CC4-072 (04_mgp6.tex:16): One hidden prediction generation was authorized; interrupted once after 432 of 540 predictions and resumed under the same frozen controls
- CC4-073 (04_mgp6.tex:16): The hidden split has been consumed; we know of no rerun and did not tune against it
- CC4-074 (04_mgp6.tex:16): Successor configuration developed on dev after hidden aggregate known (dev accuracy 0.95 and 0.961); no hidden result for it reported
- CC4-075 (04_mgp6.tex:16): Provider did not report routed model revision during development
- CC4-076 (04_mgp6.tex:16): Hidden inputs contained no gold labels; predictions hashed before private scorer; cost-matrix analysis omitted because weights committed after hidd...
- CC4-078 (04_mgp6.tex:19): Component bootstrap (60 clusters; 5,000 resamples; seed 4301): accuracy 0.8037 to 0.8889, macro-F1 0.8021 to 0.8894
- CC4-083 (04_mgp6.tex:36): Guard changed 36 of 202 model abstain outputs (30 to keep, 6 to supersede)
- CC4-084 (04_mgp6.tex:39): On dev, live controller scored 0.844 and zero-shot and four structural baselines between 0.328 and 0.367
- CC4-085 (04_mgp6.tex:39): Only live controller receives router-extracted evidence; live prompt is longer; component ablations each have their own prompt (three full payload,...
- CC4-087 (04_mgp6.tex:49-58 (Table 4)): Table 4 cell values
- CC4-091 (04_mgp6.tex:63): Design is not a clean factorial; cell E mismatched; label line differs across cells
- CC4-101 (04_mgp6.tex:67): Item-level intervals ignoring clustering differ in width and are in the supplement
- CC4-108 (04_mgp6.tex:75): Gateway may add undocumented text (prompt-token counts exceeded prompt length by roughly 2,000 tokens where comparable)
- CC4-113 (04_mgp6.tex:98-103): Figure 3 caption: five configurations under tolerant parsing, repeats as points; figure data
- CC4-149 (06_discussion.tex:7): MGP-6 labelled by deterministic rule; indexed sentences given directly to the live controller; distractors never received on hidden split; the chec...
- CC4-164 (08_appendix.tex:4): Run directory verified against output hashes in the repository derived manifest (controller judgments, report, action log; b4 judgments and report)...
- CC4-167 (08_appendix.tex:4): Manifest keys use the package name ask whereas the evaluated launcher builds its list with the earlier package name; unexplained
- CC4-168 (08_appendix.tex:6): Judgments file differs from concatenation of shard files in one field of one row; verdict fields identical in all 180 rows
- CC4-174 (08_appendix.tex:83): Transport failures (two HTTP 503 in GLM, two SSL errors in Gemini low) retried and not counted; Gemini high included after completion with one repe...
- CC4-188 (whole PDF): Frozen PDF (24 pages) has no unresolved "?" references, missing citations or table overflow that change meaning

## 4. Findings the owner should read first

1. **Annotator identifiers.** FINAL_RELEASE_READINESS.json (public repository) records annotator_a_id "ALI" and annotator_b_id "MOHAMMAD", and a dataset-owner attestation that the packets were completed by humans. The author is Ali Mohammadi. The owner statement says both annotators were independent of the author. The artifacts neither show nor refute this, and the manuscript hedges it correctly as study metadata, but it does not disclose the recorded identifiers. A skeptical reader of the repository will see the tension. Owner decision needed (CC4-067, CC4-151). I treat this as an owner-resolution item, not a contradiction.
2. **Adjudicator.** Release metadata give label_adjudication_count 0 and label_adjudication_required_count 0 (all 900 labels agreed). The manuscript says a third independent human served as adjudicator without stating that no label was adjudicated (CC4-067).
3. **Asymmetric hedging.** MGP-6 annotator independence is labelled study metadata; the LongMemEval reviewer statements (nine adjudications, three baseline overrides; 05_lme.tex:29 and :38, 06_discussion.tex:9, 08_appendix.tex:32) are in manuscript voice. No artifact records reviewer identity, date or tool (CC4-128, 130, 153, 171).
4. **V12 interruption/resume.** Manifest: three invocations (two with resume true), exit code 1, status "running", 28 abnormal worker stops (25 RuntimeError, 3 KeyboardInterrupt), 20 stale groups. The text matches, but "same frozen controls" across invocations is owner metadata; the manifest records one control set only and git_dirty_at_start true (CC4-116). The hidden-run interruption at 432 of 540 has no accessible log (CC4-072).
5. **Validator/parser status.** Commit 4fc32ca38e7ec0ff4b50897531b704289f0d3e0a exists (parent f6bf66e, local branch audit/validator-hardening); its diff is byte-identical to validator_fix.patch (SHA-256 ebaa8108ecc7...). Commit 30b4f0cd68fe67f1bec729b3e928b7b22aa6665a exists (parent f6bf66e, local branch audit/parser-json-fence-normalization); its diff is byte-identical to parser_fence_normalization.patch (SHA-256 6d5deda5aa1c...), and its blob SHA-256 9a39ce09... equals the modified working copy used by the Gemini medium and high runs. The manuscript still says the validator patch was "not applied to the repository" (03_interface.tex:32, CC4-053), which is stale; the parser "uncommitted working copy" statement is correct as historical provenance. Neither commit is on the baseline commit; I did not check any remote. The repository working tree still has mgp6_v43.py modified relative to HEAD and untracked files (read-only observation).
6. **AI-assistance disclosure** lists validator patch, reanalyses, provenance reconciliation, claim checks, drafting. Artifacts indicate the assistant workflow also produced the substitute-run runners, comparator coding behind Table 2, and figure/table scripts; the list is probably incomplete and sits in one Discussion paragraph (CC4-157).

## 5. Recomputations run (all under /tmp; commands summarised)

Environment `ask-audit` (Python 3.12, numpy 2.5.3, pydantic 2.13). Baseline export: `git archive f6bf66e... | tar x -C /tmp/ask_base_cc4` (read-only, HOME=/tmp GIT_CONFIG_GLOBAL=/dev/null git -c safe.directory=*); validator export of 4fc32ca at /tmp/ask_val_cc4; parser blob of 30b4f0c at /tmp/ask_par_cc4.

- **Substitute runs** (`/tmp/cc4_recompute_subs.py`, `cc4_recompute_subs2.py`): for each of the five results.jsonl, last row per (public_id, cell, repeat) kept (the two GLM HTTP 503 rows are superseded by retries), actions parsed with `ask.eval.mgp6_v43.parse_action_response` from the baseline export (strict) and from the 30b4f0c blob (tolerant), guard from `apply_live_controller_guard` on valid ABSTAIN, gold from public dev.jsonl; items averaged over repeats; components = (principal, memory_slot, standing_value), 20 x 9; bootstrap `rng=np.random.default_rng(0); idx=rng.integers(0,20,size=(10000,20))`, percentile 2.5/97.5 of the mean of component means.
- **Parser checks** (`cc4_checks2.py`, `cc4_checks3.py`): patched vs baseline parse equality, brace-extraction equality, fence counts, abstain/supersede counts, max reply length.
- **V12 accounting** (inline python on action_log.jsonl; counts only; range_0_179.jsonl never opened; judgments read through boolean/categorical fields only): 12,654 rows; stale rows matched by timestamp to SURPLUS_883_STALE_ROWS_822.csv; action/type/identifier counts; judgments composition; baseline judgments counts and overrides; manifest attempts.
- **R1 replay**: `ask.controller.policy.decide(FeatureSnapshot(c,e,f,r,rho), candidate_type)` for all 12,654 rows from the baseline export.
- **Hidden metrics**: numpy from the published confusion matrix (macro-F1, MCC, kappa, Wilson, ratios). No hidden labels or predictions read.
- **Tests/probes**: `PYTHONPATH=src python -m pytest -q -p no:cacheprovider <five files>` and full `tests` on both exports; `run_probes_patched.py --tree <export> --out /tmp/...` on both exports.
- **Git**: `git diff f6bf66e <commit>` compared byte-for-byte (SHA-256) with the supplement patches; `git log --diff-filter=A` for first-commit dates; `git grep ask.protocol` at f6bf66e.
- **Related work**: Table 2 parsed and compared with related_work_table_derivation.csv; selection rule re-derived from FUNCTIONAL_EQUIVALENCE_MATRIX.csv; SEARCH_LOG.csv counts; bibliography key/eprint consistency.

## 6. Recomputation discrepancy table

| Quantity | Manuscript | Recomputed | Discrepancy |
|---|---|---|---|
| Substitute accuracies, tolerant (25 cells) | Table 5 | all equal at 3 decimals | none |
| Substitute accuracies, strict (25 cells) and rejections 49/471/212/0/0 | Table parser | all equal | none |
| Paired-difference intervals (50 cells in Tables 6 and 7) | as printed | all 50 equal with first-appearance component order | 3 bounds differ by 0.01 with sorted component order (ordering unspecified in text; CC4-100) |
| Text claims on signs/ranges (A to B -0.11 to +0.40; strict +0.17/+0.40/+0.31; guard 0.025 to 0.050; 84/81 abstain; 177 of 180; 93 of 180) | Section 4 | all equal | none |
| V12 rows 12,654 = 11,832 + 822; sessions 3,547; 6.5 percent | Section 5 | equal | none |
| Keep/Supersede/Abstain, all and completed (11,478/397/779; 10,712/373/747); stale 766/24/32; types | Section 5 | equal | none |
| Keep rows with resulting id: 11,464 of 11,478 (all), 10,699 of 10,712 (completed); keep without prior 10,778 | Sections 3, 5 | equal | none |
| R1 replay of 12,654 rows | exact, deviation 0.0 | 0 action mismatches, max deviation 0.0 | none |
| Grader composition 118/8/2; 40 not sent, 32 incorrect; 128 and 137; by type | Section 5, Table 8 | equal | none |
| Clopper-Pearson intervals | 0.639 to 0.776; 0.692 to 0.821 | same | none |
| Nine adjudications (8 judge, 1 guard; 7 preference; 52 pre-failures) | Section 5 | equal | none |
| Baselines 9/80/43/114; overrides 1/0/0/2; byte identity with earlier run | Appendix | equal | none |
| Hidden metrics (458/540, Wilson, F1 0.8479, MCC 0.7728, kappa 0.7722, 38/180, 316/374) | Section 4 | equal | none; bootstrap and guard counts not recomputable |
| Tests: 34 / 672-19-9 / 98 / 132; probes 19 of 19 baseline accepted, 19 of 19 rejected by 4fc32ca, controls 8 of 8 | Section 3 | equal; the 9 failing tests are identical on both trees | none |
| Run manifest: 3 invocations, 28 stops (25+3), exit 1, status running; 17 hashes; 7/10 reachability; 912 lines; 4,301 vs 4,471 | Sections 5, 6, App. A | equal | none |
| Table 4 development values | 0.844 etc. | not recomputable (earlier run: 0.8556/0.8566 matches caption) | UNVERIFIABLE |
| Appendix re-parse of 12 + 12 directories | 24 directories | 14 directories found (12 model runs), all parse, none fenced | second set not located (CC4-179) |

## 7. Specific attention points

- 128 primary and 137 sensitivity are never merged anywhere in the text, tables or captions. No comparative LongMemEval claim exists.
- 11,832 (completed runs) versus 12,654 (merged log) is stated correctly wherever it appears; 822 and 883 and 61 accounting reproduced.
- KEEP semantics are consistent across Sections 1, 3, 4, 5 and the appendix (non-superseding decision; admission is store dependent; 11,464 of 11,478 runtime keep rows carry an identifier; MGP-6 has no store).
- Hidden data: counts and confusion matrix reproduce; structure verification is limited to public components in the text; no hidden result for another configuration is reported; the interruption at 432 of 540 is not artifact-verifiable (see above).
- Substitute-model results are never presented as manuscript-model results; the abstract compression "depend on how replies are parsed" applies to Gemini only (CC4-007, CC4-023).
- Wording: no em dashes, no priority or superlative wording found.

## 8. Release-blocking contradictions

**No.** No row is CONTRADICTED. The 14 WEAKER_THAN_CLAIM rows are wording or disclosure corrections; the annotator-identifier tension (finding 1) needs an owner decision before public release but is not a manuscript contradiction.

## 9. Are the Revision-4 edits internally consistent?

**Yes**, numerically and in cross-references: every number repeated across abstract, introduction, tables, body, appendix and captions agrees, all labels and citations resolve in the source, and the owner-supplied facts (independent annotators, adjudicator, independent reviewers, interruption and resume) appear without contradicting any artifact. The only internal inconsistency is wording asymmetry: the MGP-6 independence statements carry the "study metadata" hedge but the LongMemEval reviewer statements and the "same frozen controls" statements do not (CC4-116, 128, 130, 153, 171). The AI-disclosure scope is incomplete relative to the artifacts (CC4-157). The validator "not applied to the repository" sentence is out of date relative to the repository (CC4-053).

## 10. CSV hash and cross-check

CLAIM_CHECK4_REPORT.csv SHA-256, computed before any earlier check report was read: `1c460c8570d29067fbe98ce521b13c0ef571c37e57089693330dc73427a12e76`.

Only after freezing it did I read the Claim Check 3 report and its freeze note (verdict, evidence and fix columns). Before that I read only its claim and location columns, as instructed.

- CC3 totals: 203 supported, 28 weaker, 2 contradicted, 35 unverifiable (268 rows). Both CC3 contradictions are resolved in revision 4: the full-suite result (672 passed, 19 skipped, 9 failed) is now reported (CC3-092), and the sentence that 0.848 might not be a ceiling was replaced by the statement that substitute results do not bear on 0.848 (CC3-223). I reproduced the full-suite numbers independently.
- The CC3 weaker items I could map to revision 4 text (verification qualifier on the 40 public components, 4-element coding of search-surfaced candidates, tie rule for the twelfth neighbour, 112 iterations with 5 failures, three-nearest prior selection, constructor format-only check, false-commit definition, gateway wording, item-level interval wording, ledger wording, "at risk of removal (not tested)", "auditor" replaced by "we") are visibly addressed in revision 4. I found no reintroduced CC3 problem.
- Agreement on method: CC3 also ran a component-order sensitivity analysis; my finding that the printed intervals reproduce only with first-appearance component order is consistent with that work and is reported as CC4-100.
- Disagreement or limit on my side: CC3 recomputed the "complete development rerun" and the July run. I could find only one set of development directories, so CC4-179 (weaker, half-verified re-parse statement) reflects my search limit and is more likely a documentation gap than a manuscript error. Likewise CC4 treats Table 4 as UNVERIFIABLE where CC3 had access to a rerun recomputation (recompute_dev_complete_rerun.json); I did not read that file's values.
- New in Claim Check 4 (not covered by CC3 because the owner facts and commits are new): the reviewer/adjudicator/override wording asymmetry, the artifact-recorded annotator identifiers and zero label adjudications, the stale "not applied to the repository" sentence, the incomplete AI-assistance scope, and the "same frozen controls" attribution.
