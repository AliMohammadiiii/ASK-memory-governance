#!/usr/bin/env python3
"""R4d: compare baseline *.pre_adjudication.orig backups with the current files (ids, field names, verdict booleans, hashes only)."""
import json, sys, hashlib, os, glob, csv
RUN = sys.argv[1]
def jl(p): return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
rows = []
targets = [f'{b}' for b in ('b1', 'b2', 'b3', 'b4')] + [f'b1/_shard5', 'b4/_shard3', 'b4/_shard5']
for t in targets:
    d = f'{RUN}/{t}'
    jo = f'{d}/judgments.jsonl.pre_adjudication.orig'; jc = f'{d}/judgments.jsonl'
    if not os.path.exists(jo): continue
    o = {r['session_id']: r for r in jl(jo)}; c = {r['session_id']: r for r in jl(jc)}
    changed = []
    for q in c:
        if q in o and o[q] != c[q]:
            fields = sorted(k for k in set(o[q]) | set(c[q]) if o[q].get(k) != c[q].get(k))
            changed.append((q, fields, o[q].get('correct'), c[q].get('correct')))
    ro = json.load(open(f'{d}/report.json.pre_adjudication.orig')) if os.path.exists(f'{d}/report.json.pre_adjudication.orig') else None
    rc = json.load(open(f'{d}/report.json'))
    rows.append(dict(location=t, judgments_orig_sha256=sha(jo), judgments_current_sha256=sha(jc), n_orig=len(o), n_current=len(c), same_id_set=set(o) == set(c), n_rows_changed=len(changed), changed=changed,
        orig_correct=sum(1 for r in o.values() if r['correct']), current_correct=sum(1 for r in c.values() if r['correct']),
        report_orig_acc_x_n=(round(ro['overall_accuracy'] * ro['n_sessions'], 3) if ro else None), report_current_acc_x_n=round(rc['overall_accuracy'] * rc['n_sessions'], 3), report_orig_sha256=(sha(f'{d}/report.json.pre_adjudication.orig') if ro else None), report_current_sha256=sha(f'{d}/report.json'),
        orig_has_override_fields=any('judge_overridden' in r for r in o.values()), orig_schema_keys=len(next(iter(o.values())))))
    print(t, {k: v for k, v in rows[-1].items() if k not in ('judgments_orig_sha256', 'judgments_current_sha256', 'report_orig_sha256', 'report_current_sha256')})
json.dump(rows, open('handoff/r4_orig_backups.json', 'w'), indent=1)
