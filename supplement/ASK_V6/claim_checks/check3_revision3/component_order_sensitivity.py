"""Does the 2-decimal rounding of the cluster-bootstrap endpoints depend on the (unreported) order of the 20 components?
Orders tried: (a) sorted by first item id (used in the supplement and in recompute_models.py), (b) sorted by component key tuple, (c) reversed (a)."""
import sys, json, collections, importlib
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, '/tmp/ask_base_src')
base = importlib.import_module('ask.eval.mgp6_v43')
R = '/Users/alimohammadi/Workspace/research/ASK-memory-governance'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
recs = base.load_public_records(R + '/benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl'); byid = {r.public_id: r for r in recs}
ids = sorted(byid); pos = {i: n for n, i in enumerate(ids)}
key = lambda r: (r.memory_before['principal'], r.memory_before['memory_slot'], r.memory_before['standing_value'])
groups = collections.defaultdict(list)
for i in ids: groups[key(byid[i])].append(i)
orders = {'a_first_id': sorted(groups.values(), key=lambda g: g[0]),
          'b_key': [groups[k] for k in sorted(groups)],
          'c_reversed': sorted(groups.values(), key=lambda g: g[0])[::-1]}
rec = json.load(open(OUT + '/recompute_models.json'))
# need per-item vectors: recompute from the recompute script's module namespace is heavy; re-derive quickly
S = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/ASK_supplement'
sys.path.insert(0, '/tmp/ask_wt_src')
for k in [k for k in sys.modules if k == 'ask' or k.startswith('ask.')]: del sys.modules[k]
sys.path.remove('/tmp/ask_base_src')
wt = importlib.import_module('ask.eval.mgp6_v43')
gold = {i: byid[i].gold_action for i in ids}
RUNS = [('Gemini low', 'gemini_low'), ('Gemini medium', 'gemini_medium'), ('Gemini high (1 repeat)', 'gemini_high'), ('GLM 5.3 Flash', 'glm_5.3_flash'), ('gpt-oss-120b', 'gpt_oss_120b_medium')]
def parse(raw):
    try: return wt.parse_action_response(raw)
    except Exception: return None
per = {}
for nm, d in RUNS:
    rows = [json.loads(l) for l in open(f'{S}/substitute_runs/{d}/results.jsonl')]
    rows = [r for r in rows if r.get('action') != 'FAILED']
    act = {(r['public_id'], r['cell'], int(r['repeat'])): parse(r['raw']) for r in rows}
    reps = sorted({k[2] for k in act})
    per[nm] = {c: np.mean([[float(act[(i, c, rp)] == gold[i]) for i in ids] for rp in reps], axis=0) for c in ['A_zero_payload', 'D_zero_routed', 'E_live_payload', 'B_live_routed']}
CON = {'E-A': ('E_live_payload', 'A_zero_payload'), 'B-D': ('B_live_routed', 'D_zero_routed'), 'B-A': ('B_live_routed', 'A_zero_payload'), 'D-A': ('D_zero_routed', 'A_zero_payload'), 'B-E': ('B_live_routed', 'E_live_payload')}
rng = np.random.default_rng(0); cidx = rng.integers(0, 20, size=(10000, 20))
res = {}
for on, comps in orders.items():
    comp_of = np.zeros(180, dtype=int)
    for c, g in enumerate(comps):
        for i in g: comp_of[pos[i]] = c
    for nm in per:
        for cn, (a, b) in CON.items():
            delta = per[nm][a] - per[nm][b]
            cm = np.array([delta[comp_of == c].mean() for c in range(20)]); bc = cm[cidx].mean(1)
            res[(on, nm, cn)] = (round(float(np.percentile(bc, 2.5)), 4), round(float(np.percentile(bc, 97.5)), 4))
flips = 0; tot = 0; maxshift = 0
for nm in per:
    for cn in CON:
        ref = res[('a_first_id', nm, cn)]
        for on in ('b_key', 'c_reversed'):
            alt = res[(on, nm, cn)]; tot += 2
            for x, y in zip(ref, alt):
                maxshift = max(maxshift, abs(x - y))
                if round(x, 2) != round(y, 2): flips += 1
print('endpoint comparisons', tot * 1, 'two-decimal flips', flips, 'max shift', maxshift)
json.dump({f'{k[0]}|{k[1]}|{k[2]}': v for k, v in res.items()}, open(OUT + '/component_order_sensitivity.json', 'w'), indent=1)
