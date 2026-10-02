#!/usr/bin/env python3
"""Write R1 deliverables from the handoff JSON files (ids and hashes only)."""
import json, sys, csv, hashlib, collections, datetime
RUN = sys.argv[1]
def h(s): return hashlib.sha256(str(s).encode('utf-8')).hexdigest()[:16]
al = json.load(open('handoff/aligned_rows.json'))
procs = json.load(open('handoff/process_table.json'))
ev = json.load(open('handoff/shard_log_events.json'))
units = json.load(open('handoff/units_counts.json'))
for r in al: r['status'] = 'final' if r['proc'] == r['completing_proc'] else 'stale'
A2 = '2026-07-19T05:50:06'; A3 = '2026-07-19T08:56:03'
def attempt_of(ts):
    ts = ts[:19]
    return 1 if ts < A2 else (2 if ts < A3 else 3)
stale = [r for r in al if r['status'] == 'stale']; final = [r for r in al if r['status'] == 'final']
# worker table
kbd_ranges = collections.defaultdict(list)
for k in map(str, range(8)):
    for typ, ln, d in ev[k]['events']:
        if typ == 'KEYBOARD_INTERRUPT': kbd_ranges[k].append(ln)
deaths = json.load(open('handoff/worker_deaths.json'))
worker_rows = []
grp = collections.defaultdict(list)
for r in al: grp[(r['shard'], r['proc'])].append(r)
for d in deaths:
    s, p = d['shard'], d['proc']
    pr = [x for x in procs[str(s)] if x['proc'] == p][0]
    nxt = [x for x in procs[str(s)] if x['proc'] == p + 1]
    end_ln = nxt[0]['start_line'] if nxt else 10**9
    kbd = any(pr['start_line'] <= ln < end_ln for ln in kbd_ranges[str(s)])
    cause = 'completed' if d['end'] == 'done' else ('skipped_complete_report' if d['end'] == 'skipped_complete' else ('KeyboardInterrupt' if kbd else ('RuntimeError' if 'RuntimeError' in d['exc_classes'] else 'unclassified_exit')))
    rows_alive = grp.get((s, p), [])
    stale_rows = [r for r in rows_alive if r['status'] == 'stale']
    surviving = len(rows_alive) > 0
    worker_rows.append(dict(shard=s, worker=p, log_start_line=pr['start_line'], resume_completed_at_start=pr['resume_completed'], questions_started=len(pr['q_started']), questions_completed=len(pr['q_done']),
        end_state=cause, cascade_retry_marker_follows=d['cascade_retry_marker'], action_log_mode_at_open=('truncate (completed=0)' if pr['resume_completed'] == 0 else ('append' if pr['resume_completed'] else 'none')),
        rows_surviving_in_final_log=len(rows_alive), stale_rows=len(stale_rows), stale_question=(stale_rows[0]['q'] if stale_rows else ''),
        last_row_utc=(max(r['ts'] for r in rows_alive) if rows_alive else ''), attempt_by_timestamp=(attempt_of(max(r['ts'] for r in rows_alive)) if rows_alive else '')))
with open('WORKER_PROCESS_TABLE.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(worker_rows[0].keys())); w.writeheader(); w.writerows(worker_rows)
# stale row-level
with open('SURPLUS_883_STALE_ROWS_822.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['shard', 'action_log_row_id_in_shard', 'question_id', 'worker', 'completing_worker', 'support_session_id_sha256_16', 'candidate_text_sha256_16', 'candidate_type', 'action', 'timestamp_utc'])
    for r in sorted(stale, key=lambda r: (r['shard'], r['row_id'])): w.writerow([r['shard'], r['row_id'], r['q'], r['proc'], r['completing_proc'], r['sid_h'], r['text_h'], r['type'], r['action'], r['ts']])
# timing check: stale timestamps precede the completing rows of the same question
first_final = {}
for r in final: first_final[(r['shard'], r['q'])] = min(first_final.get((r['shard'], r['q']), '9'), r['ts'])
timing_ok = all(r['ts'] < first_final[(r['shard'], r['q'])] for r in stale)
# reuse keys (M2): text-hash+type per shard, final rows beyond cache multiplicity
cache_cnt = collections.defaultdict(collections.Counter)
cache_turnkeys = collections.defaultdict(set)
for k in range(8):
    for l in open(f'{RUN}/controller/_shard{k}/extraction_cache.jsonl', encoding='utf-8'):
        if not l.strip(): continue
        r = json.loads(l)
        for it in (r['output'].get('items') or []):
            cache_cnt[k][(h(it['text']), it.get('type_guess'))] += 1
fin_cnt = collections.defaultdict(collections.Counter); qs = collections.defaultdict(set); ss = collections.defaultdict(set)
for r in final:
    key = (r['text_h'], r['type']); fin_cnt[r['shard']][key] += 1; qs[(r['shard'], key)].add(r['q']); ss[(r['shard'], key)].add(r['sid_h'])
reuse = []
for k in range(8):
    for key in fin_cnt[k]:
        d = fin_cnt[k][key] - cache_cnt[k][key]
        if d > 0: reuse.append(dict(shard=k, text_sha256_16=key[0], type=key[1], final_rows=fin_cnt[k][key], cache_items=cache_cnt[k][key], excess=d, n_questions=len(qs[(k, key)]), n_support_sessions=len(ss[(k, key)]), question_ids=';'.join(sorted(qs[(k, key)])), support_session_sha256_16=';'.join(sorted(ss[(k, key)]))))
neg = sum(max(0, cache_cnt[k][key] - fin_cnt[k][key]) for k in range(8) for key in cache_cnt[k])
with open('SURPLUS_883_REUSE_KEYS_61.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(reuse[0].keys())); w.writeheader(); w.writerows(sorted(reuse, key=lambda x: (x['shard'], x['text_sha256_16'])))
reuse_rows = sum(x['excess'] for x in reuse)
reuse_sessions = {s for x in reuse for s in x['support_session_sha256_16'].split(';')}
reuse_q = {(x['shard'], q) for x in reuse for q in x['question_ids'].split(';')}
stale_sessions = {r['sid_h'] for r in stale}; stale_q = {(r['shard'], r['q']) for r in stale}
act_all = collections.Counter(r['action'] for r in al); act_fin = collections.Counter(r['action'] for r in final); act_st = collections.Counter(r['action'] for r in stale)
type_fin = collections.Counter(r['type'] for r in final)
# lookups
lookups = 0; hits = 0
for k in map(str, range(8)):
    for typ, ln, d in ev[k]['events']:
        if typ == 'Q_DONE': lookups += d['ext_miss']; hits += d['ext_hits']
res = dict(
  units=dict(action_log_rows=len(al), cache_entries=units['merged']['cache_entries'], cache_items=units['merged']['cache_items'], trace_rows=units['merged']['trace_rows'],
             trace_rows_with_no_llm_response=13, trace_distinct_session_turn_content=units['merged']['trace_distinct_turn_keys'], final_run_turn_lookups=lookups, final_run_cache_hits=hits, questions=180, lookups_per_question=64),
  identity=dict(surplus_as_stated=len(al) - units['merged']['cache_items'], stale_rows=len(stale), final_rows=len(final), final_minus_cache_items=len(final) - units['merged']['cache_items'], reuse_excess_rows=reuse_rows, cache_items_without_final_decision=neg),
  stale=dict(rows=len(stale), worker_deaths_with_stale_rows=len({(r['shard'], r['proc']) for r in stale}), questions=len(stale_q), distinct_support_sessions=len(stale_sessions), prefix_replay_rows_exact=822, timestamps_precede_completing_rows=timing_ok),
  reuse=dict(rows=reuse_rows, keys=len(reuse), questions=len(reuse_q), distinct_support_sessions=len(reuse_sessions), distinct_cache_entries_behind_them=27),
  actions=dict(all=dict(act_all), final=dict(act_fin), stale=dict(act_st), final_types=dict(type_fin)))
json.dump(res, open('SURPLUS_883_RECONCILIATION.json', 'w'), indent=1)
print(json.dumps(res, indent=1)); 
# stale per attempt
cnt = collections.Counter(); 
for w in worker_rows:
    if w['stale_rows']: cnt[(w['attempt_by_timestamp'], w['end_state'], w['cascade_retry_marker_follows'])] += w['stale_rows']
print(dict(cnt))
print('workers', collections.Counter((w['end_state']) for w in worker_rows))
