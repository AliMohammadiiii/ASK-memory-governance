#!/usr/bin/env python3
"""Assemble SURPLUS_883_RECONCILIATION.csv/.json from the verified intermediate results."""
import json, csv, collections
al = json.load(open('handoff/aligned_rows.json'))
base = json.load(open('SURPLUS_883_RECONCILIATION.json'))
grp = json.load(open('handoff/group_classification.json'))
wt = {(int(r['shard']), int(r['worker'])): r for r in csv.DictReader(open('WORKER_PROCESS_TABLE.csv'))}
stale = [r for r in al if r['proc'] != r['completing_proc']]
g = collections.defaultdict(list)
for r in stale: g[(r['shard'], r['proc'], r['q'])].append(r)
def cause(w): return 'M1c KeyboardInterrupt' if w['end_state'] == 'KeyboardInterrupt' else ('M1a RuntimeError then shard-level retry' if w['cascade_retry_marker_follows'] == 'True' else 'M1b RuntimeError, retry budget exhausted, next cascade attempt')
sub = collections.defaultdict(lambda: dict(rows=0, groups=0, sess=set(), qs=set()))
for (s, p, q), v in g.items():
    c = cause(wt[(s, p)]); d = sub[c]; d['rows'] += len(v); d['groups'] += 1; d['sess'] |= {r['sid_h'] for r in v}; d['qs'].add((s, q))
rows = []
m1 = base['stale']; m2 = base['reuse']
rows.append(dict(mechanism='M1 stale partial-question rows left in the append-mode action log by a worker that stopped mid-question, then re-written in full by the restarted worker', rows_explained=m1['rows'], distinct_support_sessions=m1['distinct_support_sessions'], distinct_questions=m1['questions'], worker_stops=m1['worker_deaths_with_stale_rows'],
    evidence='Per-shard action-log candidate_id resets (new worker process) aligned with ordered "ingest memory_session" progress lines; all 20 stale groups equal, in order, the first n rows of the same question rerun by the completing worker (822 of 822 rows); stale timestamps precede the completing rows; run_baseline resume code opens the log in append mode and rewrites only answers/judgments',
    confidence='high (row-level, exact)'))
for c in sorted(sub):
    d = sub[c]
    rows.append(dict(mechanism='  ' + c, rows_explained=d['rows'], distinct_support_sessions=len(d['sess']), distinct_questions=len(d['qs']), worker_stops=d['groups'], evidence='worker end state from shard log (exception class name or KeyboardInterrupt) and presence of the cascade "attempt k failed; retrying" marker', confidence='high for row counts; cause labels are log-derived'))
rows.append(dict(mechanism='M2 repeated decisions on one cached extraction output, i.e. the same turn extraction (same cache key) used by two or more questions of the same shard', rows_explained=m2['rows'], distinct_support_sessions=m2['distinct_support_sessions'], distinct_questions=m2['questions'], worker_stops='',
    evidence='After removing M1, 11,832 completing-worker rows versus 11,771 cache items: per-shard join on (candidate text hash, type) gives 61 rows of positive excess, 0 of negative excess, every excess key decided by at least 2 questions of the same shard; independent count identity 11,520 final turn lookups (180 questions x 64) minus 11,477 cache entries = 43 repeated lookups',
    confidence='high for the count (remainder of an exact partition); medium-high for the mechanism (27 of the 43 repeated lookups can be tied to items; the other 16 are not visible at item level)'))
rows.append(dict(mechanism='Unexplained', rows_explained=0, distinct_support_sessions=0, distinct_questions=0, worker_stops='', evidence='none remaining under the stated assumptions', confidence='-'))
rows.append(dict(mechanism='TOTAL explained', rows_explained=m1['rows'] + m2['rows'], distinct_support_sessions='', distinct_questions='', worker_stops='', evidence='12,654 - 11,771 = 883 = 822 + 61', confidence=''))
with open('SURPLUS_883_RECONCILIATION.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
base['mechanism_table'] = [{k: (v if not isinstance(v, set) else len(v)) for k, v in r.items()} for r in rows]
base['statement'] = '883 of 883 allocated (822 by M1, 61 by M2); 0 of 883 unexplained under the assumptions in SURPLUS_883_RECONCILIATION.md'
base['cross_checks'] = dict(duplicate_session_candidate_id_pairs=grp['dup_cand_pairs'], duplicate_pair_classes=grp['dup_pair_classes'], text_type_groups_with_multiple_decisions=grp['multi_groups'], group_classes=grp['group_classes'], groups_with_different_actions_by_class=grp['group_diff_action'])
json.dump(base, open('SURPLUS_883_RECONCILIATION.json', 'w'), indent=1)
for r in rows: print(r['rows_explained'], '|', r['distinct_support_sessions'], '|', r['distinct_questions'], '|', r['worker_stops'], '|', r['mechanism'][:90])
