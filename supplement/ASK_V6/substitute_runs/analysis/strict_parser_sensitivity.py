"""Sensitivity of Phase 16 accuracies to the reply parser.
Strict = parse_action_response from the baseline commit f6bf66e (exported to /tmp/base_p16/src).
Tolerant = the stored 'action' (produced by the working-tree parser with JSON Markdown fence normalization).
Invalid under strict is counted as incorrect. Only public development items; no benchmark text is read."""
import sys, json, glob, importlib, collections, numpy as np
sys.path.insert(0, '/tmp/base_p16/src')
import ask.eval.mgp6_v43 as base
assert base.__file__.startswith('/tmp/base_p16'), base.__file__
REPO = '/Users/alimohammadi/Workspace/research/ASK-memory-governance'
recs = base.load_public_records(REPO + '/benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl')
gold = {r.public_id: r.gold_action for r in recs}
CELLS = ['A_zero_payload', 'D_zero_routed', 'E_live_payload', 'B_live_routed']
DIRS = [('Gemini 3.8 Flash low', '../phase13_routing_check'), ('Gemini 3.8 Flash medium', 'out_ag_gemini-3.8-flash-medium'), ('Gemini 3.8 Flash high', 'out_ag_gemini-3.8-flash-high'), ('GLM 5.3 Flash', 'out_ocg_glm-5.3-flash'), ('gpt-oss-120b medium', 'out_ag_gpt-oss-120b-medium')]
out = {}
for name, d in DIRS:
    lat = {}
    for l in open(d + '/results.jsonl'):
        if l.strip():
            j = json.loads(l); lat[(j['public_id'], j['cell'], j['repeat'])] = j
    res = {}
    for c in CELLS:
        per = collections.defaultdict(list)
        for (pid, cell, rep), j in lat.items():
            if cell != c: continue
            raw = j.get('raw') or ''
            try: sa = base.parse_action_response(raw)
            except Exception: sa = None
            per[rep].append((pid, j.get('action'), sa))
        reps = sorted(per)
        tol = [np.mean([a == gold[p] for p, a, s in per[r]]) for r in reps]
        strict = [np.mean([s == gold[p] for p, a, s in per[r]]) for r in reps]
        inval = [sum(s is None for p, a, s in per[r]) for r in reps]
        fenced = [sum((j.get('raw') or '').lstrip().startswith('```') for (p, cc, rr), j in lat.items() if cc == c and rr == r) for r in reps]
        res[c] = {'n_per_repeat': [len(per[r]) for r in reps], 'tolerant_acc': float(np.mean(tol)), 'strict_acc': float(np.mean(strict)), 'strict_invalid_per_repeat': inval, 'fenced_per_repeat': fenced}
    out[name] = res
json.dump(out, open('strict_parser_sensitivity.json', 'w'), indent=1)
for n, r in out.items():
    print(n, {c: (round(v['tolerant_acc'], 3), round(v['strict_acc'], 3), v['strict_invalid_per_repeat']) for c, v in r.items()})
