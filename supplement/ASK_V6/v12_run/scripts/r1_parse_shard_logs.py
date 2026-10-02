#!/usr/bin/env python3
"""Parse controller_shard{k}.log files of the V12 run into a structured event list.
Only ids, counters and control markers are retained; no free text. Output: handoff JSON.
Usage: r1_parse_shard_logs.py RUN_DIR OUT_JSON"""
import re, sys, json, hashlib
RUN, OUT = sys.argv[1], sys.argv[2]
re_start = re.compile(r'^\[run_baseline\] baseline=controller ')
re_resume = re.compile(r'^\[run_baseline\] resume: completed=(\d+)/(\d+) remaining=(\d+)')
re_skip = re.compile(r'^\[run_baseline\] resume: existing validated complete report found')
re_loaded = re.compile(r'^\[run_baseline\] (\d+) sessions loaded')
re_q_start = re.compile(r'^\[controller\] (\S+): start; memory_sessions=(\d+) resolved=(\d+) unresolved=(\d+)')
re_q_pref = re.compile(r'^\[controller\] (\S+): memory_prefilter selected=(\d+)/(\d+) user_turns')
re_ingest = re.compile(r'^\[controller\] (\S+): ingest memory_session (\d+)/(\d+) (\S+) turns=(\d+)')
re_ext_conc = re.compile(r'^\[controller\] (\S+): memory (\d+)/(\d+): extract (\d+) user_turns concurrently')
re_ext_done = re.compile(r'^\[controller\] (\S+): memory (\d+)/(\d+): extracted (\d+) user_turns')
re_retr = re.compile(r'^\[controller\] (\S+): retrieve and answer')
re_done = re.compile(r'^\[controller\] (\S+): done; retrieved=(\d+) leakage=(\d+) extraction_cache=(\d+)/(\d+) hits relation_cache=(\d+)/(\d+) hits')
re_rdone = re.compile(r'^\[run_baseline\] done in ([0-9.]+)s')
re_attempt = re.compile(r'^\[vllm-cascade\] attempt (\d+) failed \(exit=(\d+)\); retrying in ([0-9.]+)s')
re_tb = re.compile(r'^Traceback \(most recent call last\)')
re_kbd = re.compile(r'^KeyboardInterrupt')
def sid_h(s): return hashlib.sha256(s.encode()).hexdigest()[:12]
res = {}
for k in range(8):
    path = f'{RUN}/logs/controller_shard{k}.log'
    ev = []
    for i, l in enumerate(open(path, encoding='utf-8', errors='replace'), 1):
        l = l.rstrip('\n')
        m = None
        if re_start.match(l): ev.append(('PROC_START', i, {}))
        elif (m := re_resume.match(l)): ev.append(('RESUME', i, dict(completed=int(m[1]), total=int(m[2]), remaining=int(m[3]))))
        elif re_skip.match(l): ev.append(('SKIP_COMPLETE', i, {}))
        elif (m := re_q_start.match(l)): ev.append(('Q_START', i, dict(q=m[1], n_mem=int(m[2]), resolved=int(m[3]), unresolved=int(m[4]))))
        elif (m := re_q_pref.match(l)): ev.append(('Q_PREF', i, dict(q=m[1], sel=int(m[2]), tot=int(m[3]))))
        elif (m := re_ingest.match(l)): ev.append(('INGEST', i, dict(q=m[1], idx=int(m[2]), n=int(m[3]), sid=m[4], turns=int(m[5]))))
        elif (m := re_ext_conc.match(l)): ev.append(('EXT_CONC', i, dict(q=m[1], idx=int(m[2]), n=int(m[3]), turns=int(m[4]))))
        elif (m := re_ext_done.match(l)): ev.append(('EXT_DONE', i, dict(q=m[1], idx=int(m[2]), n=int(m[3]), turns=int(m[4]))))
        elif (m := re_retr.match(l)): ev.append(('RETRIEVE', i, dict(q=m[1])))
        elif (m := re_done.match(l)): ev.append(('Q_DONE', i, dict(q=m[1], retrieved=int(m[2]), leakage=int(m[3]), ext_hits=int(m[4]), ext_miss=int(m[5]), rel_hits=int(m[6]), rel_miss=int(m[7]))))
        elif (m := re_rdone.match(l)): ev.append(('PROC_DONE', i, dict(seconds=float(m[1]))))
        elif (m := re_attempt.match(l)): ev.append(('CASCADE_RETRY', i, dict(attempt=int(m[1]), exit=int(m[2]), delay=float(m[3]))))
        elif re_tb.match(l): ev.append(('TRACEBACK', i, {}))
        elif re_kbd.match(l): ev.append(('KEYBOARD_INTERRUPT', i, {}))
    res[k] = dict(n_lines=i, events=ev)
json.dump(res, open(OUT, 'w'))
for k in range(8):
    from collections import Counter
    c = Counter(e[0] for e in res[k]['events'])
    print(k, res[k]['n_lines'], dict(c))
