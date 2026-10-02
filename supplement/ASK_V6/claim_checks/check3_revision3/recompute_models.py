"""Claim check 3: independent recomputation of the substitute-model tables from raw rows.
Read-only. Baseline parser = baseline-commit export (/tmp/ask_base_src); tolerant parser = working-tree function (/tmp/ask_wt_src).
Gold labels from the public dev file. Component = (principal, memory_slot, standing_value). 10,000 resamples, default_rng(0),
component indices drawn first (size (B,20)), then item indices (size (B,180))."""
import sys, json, collections, importlib, importlib.util
import numpy as np
sys.dont_write_bytecode = True
R = '/Users/alimohammadi/Workspace/research/ASK-memory-governance'
S = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/ASK_supplement'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'

def load_mod(root, tag):
    # import a separate copy of the package under a distinct name space by clearing sys.modules
    for k in [k for k in sys.modules if k == 'ask' or k.startswith('ask.')]:
        del sys.modules[k]
    sys.path.insert(0, root)
    m = importlib.import_module('ask.eval.mgp6_v43')
    sys.path.remove(root)
    snap = {k: v for k, v in sys.modules.items() if k == 'ask' or k.startswith('ask.')}
    return m, snap

base, base_snap = load_mod('/tmp/ask_base_src', 'base')
base_parse = base.parse_action_response
base_guard = base.apply_live_controller_guard
base_file = base.__file__
wt, wt_snap = load_mod('/tmp/ask_wt_src', 'wt')
wt_parse = wt.parse_action_response
assert base_file != wt.__file__, (base_file, wt.__file__)
ERR = (base.MGP6V43Error, wt.MGP6V43Error)

def parse(fn, raw):
    try:
        return fn(raw)
    except ERR:
        return None
    except Exception as e:  # any other exception is recorded as invalid but counted separately
        PARSE_OTHER[type(e).__name__] += 1
        return None
PARSE_OTHER = collections.Counter()

recs = base.load_public_records(R + '/benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl')
byid = {r.public_id: r for r in recs}
ids = sorted(byid)
gold = {i: byid[i].gold_action for i in ids}
ACT = ['KEEP', 'SUPERSEDE', 'ABSTAIN']
key = lambda r: (r.memory_before['principal'], r.memory_before['memory_slot'], r.memory_before['standing_value'])
groups = collections.defaultdict(list)
for i in ids: groups[key(byid[i])].append(i)
comps = sorted(groups.values(), key=lambda g: g[0])
assert len(comps) == 20 and all(len(g) == 9 for g in comps)
pos = {i: n for n, i in enumerate(ids)}
comp_of = np.zeros(180, dtype=int)
for c, g in enumerate(comps):
    for i in g: comp_of[pos[i]] = c

RUNS = [('Gemini low', 'gemini_low'), ('Gemini medium', 'gemini_medium'), ('Gemini high (1 repeat)', 'gemini_high'),
        ('GLM 5.3 Flash', 'glm_5.3_flash'), ('gpt-oss-120b', 'gpt_oss_120b_medium')]
CELLS = ['A_zero_payload', 'D_zero_routed', 'E_live_payload', 'B_live_routed']
runtime_parser = {'gemini_low': 'runner brace', 'gemini_medium': 'tolerant', 'gemini_high': 'tolerant', 'glm_5.3_flash': 'strict', 'gpt_oss_120b_medium': 'strict'}

def load_run(d):
    rows = [json.loads(l) for l in open(f'{S}/substitute_runs/{d}/results.jsonl')]
    ok = [r for r in rows if r.get('action') != 'FAILED']
    failed = [r for r in rows if r.get('action') == 'FAILED']
    cnt = collections.Counter((r['public_id'], r['cell'], int(r['repeat'])) for r in ok)
    assert max(cnt.values()) == 1, 'duplicate valid rows'
    return ok, failed

def brace_extract(raw):
    # re-implementation of the Gemini-low runner extraction (first to last brace), checked against the runner source separately
    a, b = raw.find('{'), raw.rfind('}')
    if a < 0 or b <= a: return None
    try:
        v = json.loads(raw[a:b + 1])
    except Exception:
        return None
    a_ = v.get('action') if isinstance(v, dict) else None
    return a_ if a_ in ACT else None

B = 10000
rng = np.random.default_rng(0)
cidx = rng.integers(0, 20, size=(B, 20))
iidx = rng.integers(0, 180, size=(B, 180))

def ci(delta):
    cm = np.array([delta[comp_of == c].mean() for c in range(20)])
    bc = cm[cidx].mean(1); bi = delta[iidx].mean(1)
    return {'diff': float(delta.mean()), 'ci95_cluster': [float(np.percentile(bc, 2.5)), float(np.percentile(bc, 97.5))],
            'ci95_item': [float(np.percentile(bi, 2.5)), float(np.percentile(bi, 97.5))]}

out = {'script': 'recompute_models.py', 'n_components': 20, 'B': B, 'results': {}, 'notes': {}}
for name, d in RUNS:
    ok, failed = load_run(d)
    reps = sorted({int(r['repeat']) for r in ok})
    out['notes'][name] = {'valid_rows': len(ok), 'failed_rows_dropped': len(failed), 'repeats': reps,
                          'failed_http': sorted({str(r.get('http')) for r in failed})}
    res = {}
    stored_vs = collections.Counter()
    pa = {'strict': {}, 'tolerant': {}}
    for r in ok:
        k = (r['public_id'], r['cell'], int(r['repeat']))
        raw = r['raw']
        s = parse(base_parse, raw); t = parse(wt_parse, raw)
        pa['strict'][k] = s; pa['tolerant'][k] = t
        stored = r['action'] if r['action'] in ACT else None
        rt = runtime_parser[d]
        ref = {'strict': s, 'tolerant': t, 'runner brace': brace_extract(raw)}[rt]
        stored_vs[(rt, stored == ref)] += 1
        stored_vs[('brace==tolerant', brace_extract(raw) == t)] += 1
        stored_vs[('strict==tolerant', s == t)] += 1
    out['notes'][name]['stored_action_vs_runtime_parser'] = {f'{a}|{b}': v for (a, b), v in stored_vs.items()}
    out['notes'][name]['max_raw_len'] = max(len(r['raw']) for r in ok)
    out['notes'][name]['fenced_raw'] = sum('```' in r['raw'] for r in ok)
    for rule, act in pa.items():
        per = {}; accrep = {}; invalid = {}
        for c in CELLS + ['B_guarded']:
            vals = []
            for rep in reps:
                v = []
                for i in ids:
                    a = act[(i, 'B_live_routed' if c == 'B_guarded' else c, rep)]
                    if c == 'B_guarded' and a in ACT: a = base_guard(byid[i], a)[0]
                    v.append(float(a == gold[i]))
                vals.append(np.array(v))
            per[c] = np.mean(vals, axis=0); accrep[c] = [float(x.mean()) for x in vals]
        invalid = {c: [int(sum(act[(i, c, rep)] is None for i in ids)) for rep in reps] for c in CELLS}
        n_inv = sum(1 for v in act.values() if v is None)
        con = lambda a, b: ci(per[a] - per[b])
        res[rule] = {'acc_mean': {c: float(per[c].mean()) for c in per}, 'acc_by_repeat': accrep, 'invalid_by_cell_repeat': invalid,
                     'n_invalid': n_inv, 'n_replies': len(act),
                     'contrasts': {'E-A': con('E_live_payload', 'A_zero_payload'), 'B-D': con('B_live_routed', 'D_zero_routed'),
                                   'B-A': con('B_live_routed', 'A_zero_payload'), 'D-A': con('D_zero_routed', 'A_zero_payload'),
                                   'B-E': con('B_live_routed', 'E_live_payload'), 'Bg-B': con('B_guarded', 'B_live_routed')}}
        if rule == 'tolerant':
            # prediction distributions under tolerant rule
            for c in CELLS:
                for rep in reps:
                    dist = collections.Counter(act[(i, c, rep)] for i in ids)
                    res.setdefault('pred_dist', {})[f'{c}|{rep}'] = dict(dist)
    out['results'][name] = res
out['parse_other_exceptions'] = dict(PARSE_OTHER)
json.dump(out, open(OUT + '/recompute_models.json', 'w'), indent=1)
# compact print for the checker
for name, res in out['results'].items():
    for rule in ('tolerant', 'strict'):
        r = res[rule]
        print(name, rule, {c.split('_')[0] + ('g' if 'guard' in c else ''): round(v, 3) for c, v in r['acc_mean'].items()}, 'invalid', r['n_invalid'], 'of', r['n_replies'])
print(json.dumps(out['notes'], indent=0)[:3000])
