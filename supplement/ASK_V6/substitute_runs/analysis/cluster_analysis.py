"""Phase 16 contrasts with a component-level cluster bootstrap, under two named parsers.
Parsers: baseline-strict (baseline commit parse_action_response) and json-fence-tolerant (modified working-tree function).
Actions are re-derived from the stored raw replies (parse_rows_with_module.py output). Invalid replies count as incorrect.
Clusters: the 180 public dev items form 20 components of 9 items that share (principal, memory_slot, standing_value).
Bootstrap: resample the 20 components with replacement (all 9 items travel together), 10,000 resamples, numpy default_rng(0), one index matrix shared by all contrasts.
Per-item values are averaged over repeats before resampling. Item-level intervals (earlier analysis) are kept for comparison."""
import sys, json, collections, numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, '/tmp/base_p16/src')
import ask.eval.mgp6_v43 as base
REPO = '/Users/alimohammadi/Workspace/research/ASK-memory-governance'
recs = base.load_public_records(REPO + '/benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl'); byid = {r.public_id: r for r in recs}
ids = sorted(byid); gold = {i: byid[i].gold_action for i in ids}; ACT = ['KEEP', 'SUPERSEDE', 'ABSTAIN']
key = lambda r: (r.memory_before['principal'], r.memory_before['memory_slot'], r.memory_before['standing_value'])
groups = collections.defaultdict(list)
for i in ids: groups[key(byid[i])].append(i)
comps = sorted(groups.values(), key=lambda g: g[0])
assert len(comps) == 20 and all(len(g) == 9 for g in comps), [len(g) for g in comps]
comp_of = np.zeros(180, dtype=int)
pos = {i: n for n, i in enumerate(ids)}
for c, g in enumerate(comps):
    for i in g: comp_of[pos[i]] = c
CELLS = ['A_zero_payload', 'D_zero_routed', 'E_live_payload', 'B_live_routed']
NAMES = [('../phase13_routing_check', 'Gemini 3.8 Flash (low)'), ('out_ag_gemini-3.8-flash-medium', 'Gemini 3.8 Flash (medium)'), ('out_ag_gemini-3.8-flash-high', 'Gemini 3.8 Flash (high, 1 repeat)'), ('out_ocg_glm-5.3-flash', 'GLM 5.3 Flash'), ('out_ag_gpt-oss-120b-medium', 'gpt-oss-120b (medium)')]
PAR = {'json-fence-tolerant': json.load(open('parser_provenance/parsed_json_fence_tolerant.json'))['rows'], 'baseline-strict': json.load(open('parser_provenance/parsed_baseline_strict.json'))['rows']}
B = 10000
rng = np.random.default_rng(0)
cidx = rng.integers(0, 20, size=(B, 20))      # component resamples
iidx = rng.integers(0, 180, size=(B, 180))    # item resamples (for comparison)
def ci(delta):
    cm = np.array([delta[comp_of == c].mean() for c in range(20)])
    bc = cm[cidx].mean(1); bi = delta[iidx].mean(1)
    return {'diff': float(delta.mean()), 'ci95_cluster': [float(np.percentile(bc, 2.5)), float(np.percentile(bc, 97.5))], 'ci95_item': [float(np.percentile(bi, 2.5)), float(np.percentile(bi, 97.5))]}
out = {'method': __doc__, 'n_components': 20, 'n_resamples': B, 'rng': 'numpy default_rng(0); component indices drawn first, then item indices', 'results': {}}
for d, name in NAMES:
    out['results'][name] = {'dir': d}
    for rule, rows_all in PAR.items():
        rows = rows_all[d]; reps = sorted({r[2] for r in rows})
        act = {(r[0], r[1], r[2]): r[3] for r in rows}
        per = {}; acc_rep = {}
        for c in CELLS + ['B_guarded']:
            vals = []
            for rep in reps:
                v = []
                for i in ids:
                    a = act[(i, 'B_live_routed' if c == 'B_guarded' else c, rep)]
                    if c == 'B_guarded' and a in ACT: a = base.apply_live_controller_guard(byid[i], a)[0]
                    v.append(float(a == gold[i]))
                vals.append(np.array(v))
            per[c] = np.mean(vals, axis=0); acc_rep[c] = [float(x.mean()) for x in vals]
        invalid = {c: [int(sum(act[(i, c, rep)] is None for i in ids)) for rep in reps] for c in CELLS}
        con = lambda a, b: ci(per[a] - per[b])
        out['results'][name][rule] = {'repeats': reps, 'accuracy_mean': {c: float(per[c].mean()) for c in per}, 'accuracy_by_repeat': acc_rep, 'invalid_by_repeat': invalid,
            'contrasts': {'prompt_given_payload_E-A': con('E_live_payload', 'A_zero_payload'), 'prompt_given_routed_B-D': con('B_live_routed', 'D_zero_routed'), 'routing_given_oneline_D-A': con('D_zero_routed', 'A_zero_payload'),
                          'routing_given_live_B-E': con('B_live_routed', 'E_live_payload'), 'total_B-A': con('B_live_routed', 'A_zero_payload'),
                          'guard_effect_Bg-B': con('B_guarded', 'B_live_routed')}}
json.dump(out, open('phase16_cluster_analysis.json', 'w'), indent=1)
for name in out['results']:
    for rule in PAR:
        r = out['results'][name][rule]
        print(name, rule, {c: round(v, 3) for c, v in r['accuracy_mean'].items()})
        for k, v in r['contrasts'].items(): print('    ', k, round(v['diff'], 3), 'cluster', [round(x, 3) for x in v['ci95_cluster']], 'item', [round(x, 3) for x in v['ci95_item']])
