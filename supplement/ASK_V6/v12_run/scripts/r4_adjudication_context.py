#!/usr/bin/env python3
"""R4c: context counts for the nine adjudications: controller failures before adjudication by competency, baseline verdicts on the nine ids (booleans only)."""
import json, sys, collections, csv
RUN = sys.argv[1]
def jl(p): return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
top = jl(f'{RUN}/controller/judgments.jsonl')
nine = [r['session_id'] for r in top if r.get('adjudicated')]
pre_correct = lambda r: r['correct_pre_adjudication'] if r.get('adjudicated') else r['correct']
by = collections.defaultdict(lambda: dict(n=0, raw_incorrect=0, adjudicated=0, final_incorrect=0))
for r in top:
    d = by[r['competency']]; d['n'] += 1; d['raw_incorrect'] += (not pre_correct(r)); d['adjudicated'] += bool(r.get('adjudicated')); d['final_incorrect'] += (not r['correct'])
tot = dict(n=180, raw_incorrect=sum(d['raw_incorrect'] for d in by.values()), adjudicated=sum(d['adjudicated'] for d in by.values()), final_incorrect=sum(d['final_incorrect'] for d in by.values()))
guard = {r['session_id']: not r.get('judge_was_called') for r in top if r.get('adjudicated')}
bl = {b: {r['session_id']: r['correct'] for r in jl(f'{RUN}/{b}/judgments.jsonl')} for b in ('b1', 'b2', 'b3', 'b4')}
nine_rows = []
for q in nine:
    row = {'id': q, 'competency': [r for r in top if r['session_id'] == q][0]['competency'], 'controller_judge_was_called': not guard[q]}
    for b in bl: row[f'{b}_correct'] = bl[b][q]
    nine_rows.append(row)
print(json.dumps(dict(by_competency=by, total=tot), indent=1))
print('baseline correct on the nine:', {b: sum(1 for q in nine if bl[b][q]) for b in bl})
for r in nine_rows: print(r)
# baseline failures count
print('baseline incorrect counts:', {b: sum(1 for v in bl[b].values() if not v) for b in bl})
json.dump(dict(by_competency=by, total=tot, nine=nine_rows, baseline_correct_on_nine={b: sum(1 for q in nine if bl[b][q]) for b in bl}), open('handoff/r4_context.json', 'w'), indent=1)
