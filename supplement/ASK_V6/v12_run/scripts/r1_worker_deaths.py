#!/usr/bin/env python3
"""For each worker process in each shard log: end type, exception class name only (no message text), and whether a cascade-level retry marker follows."""
import json, sys, re
RUN = sys.argv[1]
ev = json.load(open('handoff/shard_log_events.json'))
procs = json.load(open('handoff/process_table.json'))
exc_re = re.compile(r'^([A-Za-z_][\w.]*(?:Error|Exception|Interrupt|Exit|Timeout))\b')
out = []
for k in map(str, range(8)):
    lines = open(f'{RUN}/logs/controller_shard{k}.log', encoding='utf-8', errors='replace').read().split('\n')
    evs = ev[k]['events']
    for pi, p in enumerate(procs[k]):
        # find traceback event inside this process range
        start = p['start_line']
        nxt = procs[k][pi+1]['start_line'] if pi + 1 < len(procs[k]) else len(lines) + 1
        tb = [e for e in evs if e[0] in ('TRACEBACK', 'KEYBOARD_INTERRUPT') and start <= e[1] < nxt]
        retry = [e for e in evs if e[0] == 'CASCADE_RETRY' and start <= e[1] < nxt]
        exc = None; chain = []
        if tb:
            # last exception line in the segment: scan lines after the last Traceback line for the first non-indented, non-empty line
            ln = tb[-1][1]
            for j in range(ln, min(ln + 400, nxt - 1)):
                s = lines[j]
                if s and not s.startswith((' ', '\t', 'Traceback', 'During handling', 'The above exception', '[')):
                    m = exc_re.match(s)
                    if m: chain.append(m[1])
        out.append(dict(shard=int(k), proc=p['proc'], end=p['end'], resume_completed=p['resume_completed'], q_started=len(p['q_started']), q_done=len(p['q_done']),
                        exc_classes=sorted(set(chain)), cascade_retry_marker=bool(retry), start_line=start, end_line=p['end_line']))
json.dump(out, open('handoff/worker_deaths.json', 'w'), indent=1)
for o in out: print(o['shard'], o['proc'], o['end'], o['resume_completed'], o['q_started'], o['q_done'], o['exc_classes'], o['cascade_retry_marker'])
