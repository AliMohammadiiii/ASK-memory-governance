#!/usr/bin/env python3
"""Assign every per-shard action-log row to (worker process, question id, ingest event) using
(1) candidate_id resets (a new worker process restarts the counter at 1) and (2) the ordered
'ingest memory_session' progress lines of the shard log. Only ids/hashes are written.
Usage: r1_align_rows.py RUN_DIR"""
import json, sys, hashlib, collections
RUN = sys.argv[1]
procs = json.load(open('handoff/process_table.json'))
def h(s): return hashlib.sha256(s.encode('utf-8')).hexdigest()[:16]
out_rows = []   # one dict per action-log row (merged order = shard-major)
report = {}
for k in map(str, range(8)):
    rows = [json.loads(l) for l in open(f'{RUN}/controller/_shard{k}/action_log.jsonl', encoding='utf-8') if l.strip()]
    cids = [r['candidate_id'] for r in rows]
    cuts = [0] + [i for i in range(1, len(rows)) if cids[i] < cids[i-1]] + [len(rows)]
    epochs = [(cuts[i], cuts[i+1]) for i in range(len(cuts) - 1)]
    P = procs[k]
    # processes that wrote surviving rows: from the last process with resume_completed==0 and a started question
    working = [p for p in P if p['q_started']]
    last_trunc = max(i for i, p in enumerate(working) if p['resume_completed'] == 0)
    surviving = working[last_trunc:]
    assert len(surviving) == len(epochs), (k, len(surviving), len(epochs))
    done_q = {q: (p['proc']) for p in P for q in p['q_done']}
    rep = dict(n_rows=len(rows), n_epochs=len(epochs), epochs=[])
    for (a, b), p in zip(epochs, surviving):
        sub = rows[a:b]
        runs = []
        for j, r in enumerate(sub):
            if runs and runs[-1]['sid'] == r['session_id']: runs[-1]['idx'].append(a + j)
            else: runs.append(dict(sid=r['session_id'], idx=[a + j]))
        ptr = 0; matched = []; zero_events = 0
        for (q, i_, n_, sid, turns) in p['ingests']:
            if ptr < len(runs) and runs[ptr]['sid'] == sid:
                matched.append((q, i_, n_, sid, runs[ptr]['idx'])); ptr += 1
            else:
                zero_events += 1
        leftover = len(runs) - ptr
        rep['epochs'].append(dict(proc=p['proc'], rows=b - a, runs=len(runs), ingest_events=len(p['ingests']), matched_runs=ptr, zero_row_events=zero_events, leftover_runs=leftover))
        for q, i_, n_, sid, idxs in matched:
            for ix in idxs:
                r = rows[ix]
                out_rows.append(dict(shard=int(k), row_id=r['id'], proc=p['proc'], q=q, completing_proc=done_q.get(q), ingest_idx=i_, ingest_n=n_, sid_h=h(r['session_id']),
                    text_h=h(r['candidate_text']), type=r['candidate_type'], action=r['action'], cand_id=r['candidate_id'], ts=r['timestamp'], prior=r['prior_memory_id'] is not None))
    report[k] = rep
json.dump(out_rows, open('handoff/aligned_rows.json', 'w'))
json.dump(report, open('handoff/align_report.json', 'w'), indent=1)
tot = sum(len(v) for v in [out_rows])
print('aligned rows', len(out_rows))
for k in report:
    print(k, report[k]['n_rows'], [(e['proc'], e['rows'], e['runs'], e['matched_runs'], e['leftover_runs'], e['zero_row_events']) for e in report[k]['epochs']])
