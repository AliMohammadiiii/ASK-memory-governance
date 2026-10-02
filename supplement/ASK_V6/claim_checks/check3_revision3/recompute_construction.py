"""Claim check 3: public-split construction facts (Section 4): components, lengths, mean indexed position per action, pool partition.
Uses the baseline-commit router (linked_evidence_view) only to read which message positions the dialogue indexes. No text printed."""
import sys, json, collections, importlib
sys.dont_write_bytecode = True
sys.path.insert(0, '/tmp/ask_base_src')
m = importlib.import_module('ask.eval.mgp6_v43')
R = '/Users/alimohammadi/Workspace/research/ASK-memory-governance'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
res = {}
allpos = collections.defaultdict(list)
for split in ('train', 'dev'):
    recs = m.load_public_records(f'{R}/benchmarks/mgp6/mgp6_v4_3/public/{split}.jsonl')
    key = lambda r: (r.memory_before['principal'], r.memory_before['memory_slot'], r.memory_before['standing_value'])
    comps = collections.defaultdict(list)
    for r in recs: comps[key(r)].append(r)
    pos_by_action = collections.defaultdict(list)
    pair_sets = []  # per (component, length): indexed pairs per action
    lens = collections.Counter(); part_ok = 0; triples = 0; pool_sizes = collections.Counter()
    for k, rs in comps.items():
        bylen = collections.defaultdict(dict)
        for r in rs:
            v = m.linked_evidence_view(r)
            ps = [it['message_position'] for it in v['indexed_evidence']]
            pos_by_action[r.gold_action].extend(ps); allpos[r.gold_action].extend(ps)
            bylen[len(r.dialogue)][r.gold_action] = (ps, v['evidence_routing']['available_numbered_message_count'])
            pool_sizes[v['evidence_routing']['available_numbered_message_count']] += 1
        for L, d in bylen.items():
            triples += 1
            sets = [set(d[a][0]) for a in d]
            ok = len(d) == 3 and all(len(s) == 2 for s in sets) and len(set().union(*sets)) == 6 and sum(len(s) for s in sets) == 6
            part_ok += ok
        lens.update(len(r.dialogue) for r in rs)
    allp = [p for a in pos_by_action.values() for p in a]
    res[split] = {'n': len(recs), 'components': len(comps), 'component_sizes': dict(collections.Counter(len(v) for v in comps.values())), 'lengths': dict(lens),
                  'mean_indexed_position_by_action': {a: round(sum(v) / len(v), 4) for a, v in pos_by_action.items()},
                  'mean_indexed_position_all': round(sum(allp) / len(allp), 4), 'triples': triples, 'triples_partition_ok': part_ok, 'numbered_message_count': dict(pool_sizes)}
allp = [p for a in allpos.values() for p in a]
res['pooled'] = {'mean_indexed_position_all': round(sum(allp) / len(allp), 4), 'by_action': {a: round(sum(v) / len(v), 4) for a, v in allpos.items()}}
json.dump(res, open(OUT + '/recompute_construction.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
