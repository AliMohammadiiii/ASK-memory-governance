#!/usr/bin/env python3
"""Routing x prompt decomposition on the public MGP-6 v4.3 dev split, several substitute models. Item-level only. Latest row per (item, cell, repeat) is used; FAILED rows are reported, not scored as correct."""
import json, sys, os, glob, collections
import numpy as np
REPO = '/Users/alimohammadi/Workspace/research/ASK-memory-governance'
sys.dont_write_bytecode = True; sys.path.insert(0, REPO + '/src')
from ask.eval.mgp6_v43 import load_public_records, apply_live_controller_guard
recs = load_public_records(REPO + '/benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl'); byid = {r.public_id: r for r in recs}
ids = sorted(byid); gold = {i: byid[i].gold_action for i in ids}; ACT = ['KEEP', 'SUPERSEDE', 'ABSTAIN']
CELLS = ['A_zero_payload', 'D_zero_routed', 'E_live_payload', 'B_live_routed']
def mf1(y, p):
    f = []
    for c in ACT:
        tp = sum(g == c and q == c for g, q in zip(y, p)); fp = sum(g != c and q == c for g, q in zip(y, p)); fn = sum(g == c and q != c for g, q in zip(y, p))
        f.append(0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f))
out = {}
rng = np.random.default_rng(0); B = 10000; idx = rng.integers(0, 180, size=(B, 180))
for d in ['../phase13_routing_check'] + sorted(glob.glob('out_*')):
    f = d + '/results.jsonl'
    if not os.path.exists(f): continue
    lat = {}
    for l in open(f, encoding='utf-8'):
        if l.strip(): j = json.loads(l); lat[(j['public_id'], j['cell'], j['repeat'])] = j
    reps = sorted({k[2] for k in lat}); model = next(iter(lat.values())).get('requested_model')
    m = {'dir': d, 'model': model, 'rows': len(lat), 'repeats_present': reps, 'cells': {}}
    corr = {}
    complete = True
    for c in CELLS + ['B_guarded']:
        m['cells'][c] = {}
        for rep in reps:
            src = 'B_live_routed' if c == 'B_guarded' else c
            rr = {i: lat.get((i, src, rep)) for i in ids}
            n_have = sum(1 for v in rr.values() if v is not None)
            if n_have < 180: complete = False; m['cells'][c][rep] = {'n_have': n_have}; continue
            pred = []
            for i in ids:
                a = rr[i]['action']
                if c == 'B_guarded' and a in ACT: a = apply_live_controller_guard(byid[i], a)[0]
                pred.append(a)
            y = [gold[i] for i in ids]
            m['cells'][c][rep] = {'accuracy': float(np.mean([g == p for g, p in zip(y, pred)])), 'macro_f1': mf1(y, pred), 'invalid_or_failed': sum(p not in ACT for p in pred),
                                  'n_failed_transport': sum(1 for i in ids if rr[i]['action'] == 'FAILED'), 'pred_abstain': pred.count('ABSTAIN'), 'finish_length': sum(1 for i in ids if rr[i].get('finish_reason') == 'length')}
            if c in CELLS: corr.setdefault(c, {})[rep] = np.array([float(g == p) for g, p in zip(y, pred)])
    m['complete'] = complete
    if complete and len(reps) >= 1:
        cm = {c: np.mean([corr[c][r] for r in reps], axis=0) for c in CELLS}
        def con(a, b):
            dlt = cm[a] - cm[b]; bs = dlt[idx].mean(1)
            return {'diff': float(dlt.mean()), 'ci95': [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}
        m['contrasts'] = {'prompt_given_payload_E-A': con('E_live_payload', 'A_zero_payload'), 'prompt_given_routed_B-D': con('B_live_routed', 'D_zero_routed'),
                          'routing_given_zero_D-A': con('D_zero_routed', 'A_zero_payload'), 'routing_given_live_B-E': con('B_live_routed', 'E_live_payload'), 'total_B-A': con('B_live_routed', 'A_zero_payload')}
    out[d] = m
json.dump(out, open('multi_model_analysis.json', 'w'), indent=1)
for d, m in out.items():
    print(d, m['model'], 'rows', m['rows'], 'reps', m['repeats_present'], 'complete', m['complete'])
    for c in CELLS + ['B_guarded']:
        print('   ', c, {r: (round(v['accuracy'], 3) if 'accuracy' in v else v) for r, v in m['cells'][c].items()}, 'inv', {r: v.get('invalid_or_failed') for r, v in m['cells'][c].items()}, 'len', {r: v.get('finish_length') for r, v in m['cells'][c].items()})
    for k, v in m.get('contrasts', {}).items(): print('   ', k, round(v['diff'], 3), [round(x, 3) for x in v['ci95']])
