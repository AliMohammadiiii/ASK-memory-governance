#!/usr/bin/env python3
"""Segment parsed shard-log events into worker processes and tabulate questions started/completed per process."""
import json, sys, collections
ev = json.load(open('handoff/shard_log_events.json'))
procs = {}   # shard -> list of dict
for k in map(str, range(8)):
    cur = None; L = []
    for typ, ln, d in ev[k]['events']:
        if typ == 'PROC_START':
            cur = dict(shard=int(k), proc=len(L), start_line=ln, resume_completed=None, skip=False, q_started=[], q_done=[], ingests=[], end='open', end_line=None, seconds=None)
            L.append(cur); continue
        if cur is None: continue
        if typ == 'RESUME': cur['resume_completed'] = d['completed']
        elif typ == 'SKIP_COMPLETE': cur['skip'] = True; cur['end'] = 'skipped_complete'
        elif typ == 'Q_START': cur['q_started'].append(d['q'])
        elif typ == 'Q_DONE': cur['q_done'].append(d['q'])
        elif typ == 'INGEST': cur['ingests'].append((d['q'], d['idx'], d['n'], d['sid'], d['turns']))
        elif typ == 'PROC_DONE': cur['end'] = 'done'; cur['seconds'] = d['seconds']; cur['end_line'] = ln
        elif typ in ('TRACEBACK', 'KEYBOARD_INTERRUPT') and cur['end'] == 'open':
            cur['end'] = 'killed' if typ == 'KEYBOARD_INTERRUPT' else 'traceback'; cur['end_line'] = ln
    procs[k] = L
json.dump(procs, open('handoff/process_table.json', 'w'))
print('shard proc start_line resume_completed end q_started q_done ingests')
for k in map(str, range(8)):
    for p in procs[k]:
        inflight = [q for q in p['q_started'] if q not in p['q_done']]
        print(k, p['proc'], p['start_line'], p['resume_completed'], p['end'], len(p['q_started']), len(p['q_done']), len(p['ingests']), 'inflight=%d' % len(inflight))
