import csv, json, collections, hashlib
O = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3/'
rows = list(csv.DictReader(open(O + 'CLAIM_CHECK3_REPORT.csv', encoding='utf-8')))
V = ['SUPPORTED', 'WEAKER_THAN_STATED', 'CONTRADICTED', 'UNVERIFIABLE']
ct = collections.OrderedDict()
for r in rows: ct.setdefault(r['area'], collections.Counter())[r['verdict']] += 1
tot = collections.Counter(r['verdict'] for r in rows)
sha = hashlib.sha256(open(O + 'CLAIM_CHECK3_REPORT.csv', 'rb').read()).hexdigest()
frozen = open(O + 'freeze_hash_before_crosscheck.txt').read().split()
L = []
w = L.append
w('# Claim check 3 (revision 3 of the arXiv draft)')
w('')
w('Independent claim check of main.tex, author_info.tex, sections 00 to 08 and the four generated tables. Report only: nothing under ASK-memory-governance and nothing in the draft directory was edited (the repository working tree has two modified and three untracked files that were already present; they were recorded, not touched). Evidence was read from a `git archive` export of baseline commit f6bf66e (under /tmp), the supplement, raw per-call rows of the substitute runs (public development items only), the V12 backup run directory (ids, counts and hashes only) and the July development runs. No network and no paid call was made. No benchmark or LongMemEval text is reproduced in any output.')
w('')
w('## Items I could not check, or checked only in part (read first)')
w('')
w('1. **Hidden MGP-6 split.** Hidden labels, predictions, component map and per-probe shortcut accuracies are private. Hidden-split numbers (0.8481, confusion matrix, Wilson and cluster intervals, guard counts, safety rates) were compared with the tracked aggregate JSON and the final hidden report only; the cluster bootstrap for the hidden split was not recomputed. The pool structure was recomputed on the 40 public components only.')
w('2. **Related work.** The search was not re-run and the 30 + 12 source papers were not re-read. The 26 sentences of Section 2 that describe other works (CC3-036 to CC3-061) are UNVERIFIABLE by me; for each I report that the claim-trace passage is consistent with the sentence and that the bibliography key matches the supplied identity files (32 of 35 bibliography entries match on arXiv id and title; Persona matches by title and DOI; the HKUDS MGP specification matches its dossier row; LongMemEval arXiv 2410.10813 is not in the supplied files). What I did verify: the 72 table cells, the counts 30, 12, 112, and the selection rule.')
w('3. **Figures.** fig_models.pdf and fig_lme.pdf were opened for visual inspection but I cannot report their marks; I checked the data arrays and the generating scripts instead (CC3-171 is UNVERIFIABLE for the rendered graphic).')
w('4. **Compilation.** There is no TeX compiler here. The draft was not compiled; I ran static checks only (citations, labels and references, environments, brace and dollar balance, input and figure files, banned words, dashes). Tests were run under Python 3.12 only; Python 3.11 was not tested.')
w('5. **V12 run internals not re-derived.** The slice file and all answer, prediction and rationale text were not opened. I re-derived from counts: the 12,654-row accounting, R1 replay, the 20 stale groups (uniquely located contiguous runs, all 822 rows), the 11,771 item count, the grader composition, adjudication counts, baseline overrides, coverage, hashes, worker-stop counts (from shard-log markers). I did not re-derive: that each stale group is the leading prefix of its question (needs question alignment from shard progress logs), the 61-row mechanism, the 16 of 43 uncharacterised lookups, the 23 session-field disagreements and the single trace row without cache entry (SURPLUS_883_RECONCILIATION.md assumptions A1 to A6). The backup git object store was not re-queried for Appendix A reachability; I used the manifest CSV and re-hashed the 17 files in the shipped tarball.')
w('6. **Request bodies** of the V12 answer calls and of the substitute runs are not logged. "Seed 0 was sent" rests on the recovered client code and the seed field of the answers; the "gateway adds text" statement rests on a prompt-token gap that is consistent with it but is not a test.')
w('7. **Process statements** (substitute models chosen after inspecting Gemini low and by one-request tests; Gemini high still running when first analysed; Kimi and MiMo reports; hidden split not re-run; who annotated) have no record and are UNVERIFIABLE.')
w('')
w('Transparency note: the task context carried a memory note with aggregate counts of the earlier checks (not their row verdicts); I did not use it as evidence, and I opened the two earlier report directories only after my CSV was frozen.')
w('')
w('Declared reductions of scope: none by sampling or capping. Every substitute-run row (1440 + 1440 + 720 + 1442 + 1440; 8 DeepSeek), every one of the 12,654 log rows and every public dev item was processed. Hidden, LongMemEval-text and literature material were deliberately not accessed or not re-run as listed above.')
w('')
w('## Verdict counts')
w('')
w('%d rows. CSV SHA-256 `%s`. The CSV was written and hashed (`%s`, %s UTC) before check 1 and check 2 were opened; it was not edited afterwards.' % (len(rows), sha, frozen[-2] if len(frozen) > 1 else '', frozen[-1]))
w('')
w('| Area | SUPPORTED | WEAKER_THAN_STATED | CONTRADICTED | UNVERIFIABLE | Total |')
w('|---|---:|---:|---:|---:|---:|')
for a, c in sorted(ct.items(), key=lambda x: -sum(x[1].values())):
    w('| %s | %d | %d | %d | %d | %d |' % (a, c['SUPPORTED'], c['WEAKER_THAN_STATED'], c['CONTRADICTED'], c['UNVERIFIABLE'], sum(c.values())))
w('| **All** | **%d** | **%d** | **%d** | **%d** | **%d** |' % (tot['SUPPORTED'], tot['WEAKER_THAN_STATED'], tot['CONTRADICTED'], tot['UNVERIFIABLE'], len(rows)))
w('')
w('Area labels follow the request; DISCLOSURE and PRESENTATION are added for sentences that are not claims about evidence. Rows are one claim or a tightly coupled group of claims (a table counts as one row when every cell was compared).')
w('')
w('## Non-SUPPORTED items and minimal fixes')
w('')
w('Contradicted (2):')
w('')
for r in rows:
    if r['verdict'] == 'CONTRADICTED':
        w('- **%s** (%s:%s, %s). Claim: "%s". Evidence: %s **Fix:** %s' % (r['id'], r['file'].replace('sections/', ''), r['location'], r['area'], r['claim'].replace('\n', ' ')[:260], r['evidence'].replace('\n', ' '), r['fix']))
w('')
w('Weaker than stated (%d):' % tot['WEAKER_THAN_STATED'])
w('')
w('| ID | Location | Area | Issue (short) | Fix |')
w('|---|---|---|---|---|')
for r in rows:
    if r['verdict'] == 'WEAKER_THAN_STATED':
        ev = r['evidence'].replace('\n', ' ').replace('|', '/')
        w('| %s | %s:%s | %s | %s | %s |' % (r['id'], r['file'].replace('sections/', ''), r['location'], r['area'], ev[:330] + ('...' if len(ev) > 330 else ''), r['fix'].replace('|', '/')))
w('')
un = [r for r in rows if r['verdict'] == 'UNVERIFIABLE']
w('Unverifiable (%d):' % len(un))
w('')
lit = [r['id'] for r in un if r['file'].endswith('02_related_work.tex') and r['claim'][:6] != 'Within']
w('- %d Section 2 sentences about other works: %s to %s (see item 2 above).' % (len(lit), lit[0], lit[-1]))
for r in un:
    if r['id'] in lit: continue
    w('- **%s** (%s:%s): "%s" Reason: %s' % (r['id'], r['file'].replace('sections/', ''), r['location'], r['claim'].replace('\n', ' ')[:170], r['evidence'].replace('\n', ' ')[:300]))
w('')
w('## Recomputation discrepancy table')
w('')
w('Scripts and JSON are in this directory. "Match" means agreement at the precision printed in the paper.')
w('')
w('| Quantity (paper location) | Paper | Recomputed from raw evidence | Status | Output |')
w('|---|---|---|---|---|')
T = [
('Table models-acc, 25 accuracies (04:78-81)', 'as printed', 'identical at 3 decimals', 'match', 'recompute_models.json, compare_tables.py'),
('Tables models-prompt and models-routing, 25 contrasts with 95% component-cluster intervals (04:83-95)', 'as printed', '25 differences at 3 decimals and 50 endpoints at 2 decimals agree (default_rng(0), 10,000 resamples, 20 components of 9); supplement JSON agrees exactly (60 contrasts, max abs diff 0)', 'match', 'recompute_models.json'),
('Component order of the bootstrap (not stated)', 'n/a', 'other orders shift 8 of 100 endpoints by at most 0.006; "interval includes zero" never changes', 'note', 'component_order_sensitivity.json'),
('Item-level intervals "slightly narrower" (04:66)', 'narrower', 'narrower in 24 of 30 tolerant contrasts, wider in 6 (gpt-oss up to +29%)', 'DISCREPANCY (CC3-157)', 'recompute_models.json'),
('Parser sensitivity table, 50 accuracies and 10 rejected counts (08:107-112)', 'as printed; 49/1440, 471/1440, 212/720, 0, 0', 'identical', 'match', 'recompute_models.json'),
('Stored action vs parser used at run time', 'low: brace extraction; medium, high: modified working copy; GLM, gpt-oss: baseline parser', 'stored action equals that parser on 1440/1440, 1440/1440, 720/720, 1440/1440, 1440/1440 rows', 'match', 'recompute_models.json notes'),
('Gemini high cell A strict 0.478, 93 fenced of 180 (04:72)', '0.478; 93', '0.478; 93 invalid of 180 (all fenced); 87 of them correct under the tolerant rule', 'match', 'recompute_models.json'),
('Predicted ABSTAIN 84 and 81 (Gemini high, live); gpt-oss 177 SUPERSEDE (04:70,72)', '84, 81, 177', '84, 81, 177', 'match', 'recompute_models.json pred_dist'),
('Prompt hashes of the substitute runs vs repository builders', '"repository builders"', 'sha256 of rebuilt prompt equals stored prompt_sha256 in all 6,480 valid rows', 'match', 'prompt_token_gap.json'),
('Prompt-token excess "roughly 2,000" (04:74)', '~2,000', '1,924 to 2,056 (GLM, gpt-oss), 2,184 to 3,041 (Gemini low, medium), approximate (chars/4)', 'match (approximate)', 'prompt_token_gap.json'),
('DeepSeek record (08:85)', '5 items, 8 records; 3+1 at 1,024; 3+1 at 4,096', '5 distinct ids, 8 rows; 1,024: 3 empty (attempts 3, 1,024 reasoning tokens), 1 answered (725 tokens); 4,096: 4 empty (finish length)', 'match', 'inline (substitute_runs/deepseek_not_used)'),
('Qwen smoke records (08:85)', '"reported as unavailable", 2 records', '2 records, HTTP 400 Bad Request, model qwen3.5-plus', 'DISCREPANCY (CC3-248)', 'phase16 smoke file'),
('July development reply check (08:113)', '14 directories of the manuscript model, 180 replies each, none fenced', '14 directories, 180 each, 0 invalid, 0 fenced; but 2 are rule controllers; and Table dev comes from a different rerun (12 directories, also 0 invalid, 0 fenced)', 'DISCREPANCY in population (CC3-257); conclusion holds', 'recompute_july_dev.json, recompute_dev_complete_rerun.json'),
('Table dev, 10 rows x accuracy and macro-F1 (04:44-58)', 'as printed', 'identical at 3 decimals from the complete rerun predictions; frozen dev run 0.8556/0.8566 also reproduced', 'match', 'recompute_dev_complete_rerun.json, recompute_dev_table.json'),
('Hidden aggregate: 0.8481, 458/540, confusion, CIs, MCC, kappa, guard 36/202, false-commit 38/180', 'as printed', 'identical to tracked JSON (labels not accessed)', 'match (aggregate only)', 'ASK repo analysis JSON'),
('Pool structure: 3.600, 3.575, 3.5875; 120 triples; pairs partition the pool; numbering permuted', 'as printed', 'identical (train and dev, text hashes)', 'match (public only)', 'recompute_construction.json, recompute_pool_structure.json'),
('MGP-6 v2: 180 = 90/66/24; lookup exact', 'as printed', 'identical; lookup accuracy 1.0 on the 90 held-out rows', 'match', 'recompute_v2.json'),
('V12 grader: 128/137; 118/8/2; 40 unjudged, 32 incorrect; 9 adjudications (8 judge, 1 guard; 7/1/1 by type); CP intervals; 8 of 9 abstention', 'as printed', 'identical', 'match', 'recompute_v12_grader.json'),
('Decision log: 12,654 rows; 3,547 sessions; 11,832 + 822; 6.5%; actions 10,712/373/747 (0.905/0.032/0.063); types 9,192/2,273/367; stale 766/24/32; all 11,478/397/779; Keep with id 10,699 and 11,464', 'as printed', 'identical (822 matched uniquely by timestamp; text hash, action, type equal)', 'match', 'recompute_v12_log_accounting.json'),
('20 stale groups equal the leading rows of the re-run (822/822)', 'as printed', '20 of 20 groups are unique contiguous runs of the completed log (822 rows); "leading" not re-derived', 'match (partial)', 'recompute_stale_prefix.json'),
('11,771 items; 883 = 822 + 61; 11,520 - 11,477 = 43', 'as printed', 'cache 11,477 entries with 11,771 items; trace 11,491 rows with 11,771 items (13 rows empty); arithmetic holds', 'match', 'inline'),
('R1 replay of 12,654 rows, max deviation 0.0', 'as printed', '0 mismatches in action, scores, thresholds; rationale strings equal', 'match', 'recompute_r1_replay.json'),
('28 worker stops (25 runtime errors, 3 interruptions)', 'as printed', 'shard logs: 25 RuntimeError lines, 3 KeyboardInterrupt lines', 'match', 'inline'),
('Coverage: 180 ids once each; id hash', 'as printed', '180 distinct ids in three merged files; sorted-id sha256 equals manifest 93ee0e5e...', 'match', 'inline'),
('Baseline counts 9 (10), 43, 80, 114 (112); byte identity with the earlier run', 'as printed', 'identical; all four baselines byte-identical in the earlier run', 'match', 'recompute_baselines.json'),
('Evaluated code: 17/17 hashes, 7 reachable, 10 unreferenced, 912 lines, 4,301 vs 4,471, 11/2/4', 'as printed', 'identical (manifest CSV + tarball re-hash)', 'match', 'recompute_evaluated_code.json'),
('Validator: baseline 19/19 accepted; patched 19/19 rejected; 8 controls; 34, 98, 132 tests', 'as printed', 'identical on clean exports', 'match', 'probe_results_*_check3.json, validator_pytest_recheck.txt'),
('Full test suite at baseline "not run" (03:32)', 'not run', 'run on the export (672 passed, 19 skipped, 9 failed) in PYTEST_RESULTS.txt section G', 'DISCREPANCY (CC3-092)', 'supplement validator/PYTEST_RESULTS.txt'),
('Neighbors table: 72 cells; twelve selected', 'as printed', '72/72 cells reproduce; twelfth place is a tie (CC3-063)', 'match; selection note', 'recompute_neighbors_table.json'),
('Search counts 30, 12, 112', 'as printed', '30 dossiers, 12 close candidates, 112 searches (+6 identifier resolutions; 5 searches returned no records)', 'match; qualifier needed (CC3-066)', 'SEARCH_LOG.csv'),
]
for t in T: w('| ' + ' | '.join(x.replace('|', '/') for x in t) + ' |')
w('')
w('Previously contradicted statements (check 1: CC-044, CC-113, CC-126, CC-136, CC-142, CC-158, CC-161; check 2: CC2-MGP-08, CC2-LME-05, CC2-APP-15) are all corrected in revision 3: seed 0 is described as sent; the 64-zero identity is a separate observation; the homogeneity check is described as recorded; 38 of 82 is "the largest share"; 118 model judge and 8 guards; the mean indexed position is stated per split; the DeepSeek counts are 3+1 and 3+1; the claims table reads "The validator rejects non-conforming states: Not supported".')
w('')
w('## Disagreements with check 1 and check 2 (read after my verdicts were frozen)')
w('')
w('Check 1 reviewed revision 0 and check 2 revision 1, so most earlier findings were already addressed. Where a current sentence matches an earlier row and my verdict differs:')
w('')
w('| Topic | Earlier verdict | My row and verdict | Reason for the difference |')
w('|---|---|---|---|')
D = [
('"we did not run the full suite there" (03:32)', 'CC2-INT3-14 SUPPORTED (revision 1: "we did not rerun the full suite")', 'CC3-092 CONTRADICTED', 'Evidence produced after check 2: the validator work recorded a full-suite run on the baseline export (672 passed, 19 skipped, 9 failed; PYTEST_RESULTS.txt section G).'),
('"a prior is chosen by embedding similarity" (03:23)', 'CC-032, CC2-INT3-08 SUPPORTED', 'CC3-082 WEAKER', 'Same facts (top-3 in V12), different threshold: the prior is the first relation-qualified neighbour among three, with a similarity threshold and a numeric-supersede shortcut; the default path (k=1) uses the newest same-type memory.'),
('"a local gateway" (04:62, 08:70)', 'CC2-MGP-39, CC2-APP-18 SUPPORTED', 'CC3-143, CC3-243 WEAKER', 'The Gemini low runner posts to a remote tunnel hostname, not localhost:20128.'),
('"cells with the live prompt are optimistic" (04:74)', 'CC2-MGP-52 SUPPORTED', 'CC3-167 WEAKER', 'Selection on the dev split was done with the manuscript model; optimism for substitute models is a conjecture.'),
('"0.961 ... not a ceiling" (06:7)', 'CC2-DIS-09 WEAKER (fix adopted: "suggests, but does not show")', 'CC3-223 CONTRADICTED', 'After the hedge was adopted, the sentence still draws a hidden-split inference from the substitute stream, which Table 1 and Section 4 exclude. Severity differs; I agree the numbers are right.'),
('"A high score reflects the model ... applying the decision criteria" (06:7)', 'CC2-DIS-06 WEAKER (fix adopted: "measures" became "reflects")', 'CC3-219 WEAKER', 'Residual: "reflects" is still a mechanism claim; suggest "is consistent with".'),
('Qwen "reported as unavailable" (08:85)', 'CC2-APP-14 UNVERIFIABLE', 'CC3-248 WEAKER', 'I located the smoke file: both records are HTTP 400 for qwen3.5-plus; the file is not in the manifest.'),
('"false-commit" for KEEP predictions (04:35, 06:3)', 'CC2-MGP-29 SUPPORTED; CC-136 CONTRADICTED (fixed)', 'CC3-130, CC3-133, CC3-212 WEAKER', 'New in revision 3: KEEP was redefined as non-superseding, so counting predicted KEEP as a "commit" conflicts with the paper\'s own definition; also the sentence at 04:35 about "the KEEP label" on gold-ABSTAIN items is unclear.'),
('MemTrace cited for final-answer-only evaluation (01:3)', 'CC2-INT-02 WEAKER (fix adopted: citations added)', 'CC3-012 WEAKER', 'The added citation 2606.17328 is a paper titled around what final accuracy misses; Section 2 describes it as separating retrieval from evidence use.'),
('Item-level intervals "slightly narrower" (04:66)', 'not checked (new sentence)', 'CC3-157 WEAKER', 'Narrower in 24 of 30, wider in 6.'),
('Failure ledger covers the baseline overrides (05:38)', 'not checked (reworded in revision 3)', 'CC3-195 WEAKER', 'F10 describes five v7 overrides, not the three in the V12 baselines.'),
('July development replies (08:113)', 'not checked (new in revision 3)', 'CC3-257 WEAKER', '14 directories include 2 rule controllers and are not the source of Table dev.'),
('Abstract "three streams" vs Table 1', 'CC2-ABS-04 WEAKER (three versus four)', 'not raised', 'Table 1 now has five rows (v4.3 hidden, v2, V12 run, V12 log, substitute dev) against "three streams" in the abstract. I treated v2 and the log as sub-streams; this residual is minor but unresolved.'),
('Section 2 (related work), bibliography', 'not checked by CC2; CC-011 UNVERIFIABLE', 'CC3-035 to CC3-069', 'I checked the table, counts, selection rule and bibliography identity against the supplied files; sentence-level content remains UNVERIFIABLE.'),
]
for d in D: w('| ' + ' | '.join(x.replace('|', '/') for x in d) + ' |')
w('')
w('Earlier rows I could match to current text and found fixed: CC2-ABS-02, ABS-05 (partly, see CC3-002), INT-04, MGP-16, MGP-21, MGP-41, MGP-46, MGP-51 (component bootstrap now stated; ordering still unstated), LME-16, LME-19, LME-20, LME-24, LME-26, APP-13, D-04, CON-05. I did not re-adjudicate every earlier row. The 2,000-token overhead and 117/9 versus 118/8 grader counts agree with check 2 and with this check.')
w('')
w('## Additional observations (not scored as claims)')
w('')
w('- Most KEEP rows in the V12 log have no compared prior: 10,778 of 11,478 (93.9%); only 686 carry a prior and a resulting id, and the 14 without a resulting id all carry a prior (duplicate suppression). This supports the KEEP wording in Section 3 and could be stated there.')
w('- The claim trace marks all 26 sentences about other works as DIRECT support (only its sentences 1, 29 and 30 are INDIRECT). Section 2 sentences 29 and 36 (table lead-in and scope paragraph) differ from the trace text, which was written at 12:21 while Section 2 was last saved at 17:32; I re-checked both (CC3-063, CC3-066, CC3-067).')
w('- The annotation release record names annotators with bare first-name-like identifiers that resemble the author\'s name; the paper makes no independence claim, which is correct. Stating who annotated would let readers judge.')
w('- `figures/fig_twobytwo.*` is unused; label `tab:parser` is never referenced; `make_multimodel_assets.py` reads a path outside the shipped supplement (CC3-268).')
w('- Hidden-run bootstrap used 5,000 resamples with seed 4301 (report); the paper does not state the count for the hidden-split intervals.')
w('')
w('## Files')
w('')
w('- `CLAIM_CHECK3_REPORT.csv`: 268 rows (id, area, file, location, claim, verdict, evidence, fix).')
w('- Recompute scripts and outputs: `recompute_models.py/.json`, `compare_tables.py`, `component_order_sensitivity.py/.json`, `recompute_july_dev.py/.json`, `recompute_dev_complete_rerun.py/.json`, `recompute_dev_table.py/.json`, `recompute_construction.py/.json`, `recompute_pool_structure.py/.json`, `recompute_requested_value.json`, `recompute_v2.json`, `recompute_v12_grader.py/.json`, `recompute_v12_log_accounting.py/.json`, `recompute_stale_prefix.py/.json`, `recompute_r1_replay.py/.json`, `recompute_baselines.py/.json`, `recompute_evaluated_code.py/.json`, `recompute_neighbors_table.py/.json`, `prompt_token_gap.py/.json`, `bib_identity_check.py/.json`, `static_checks.py/.json`, `static_word_hits.json`, `probe_results_baseline_check3.json`, `probe_results_patched_check3.json`, `validator_pytest_recheck.txt`.')
w('- Row sources: `rows_part1.py` to `rows_part5.py`, `build_report.py`, `build_summary.py`. Parsers were imported from read-only exports under /tmp (`ask_base_src` baseline, `ask_wt_src` copy of the modified working-tree file); bytecode writing was disabled.')
open(O + 'CLAIM_CHECK3_SUMMARY.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
txt = '\n'.join(L)
assert '\u2014' not in txt and '\u2013' not in txt
print(len(L), 'lines')
