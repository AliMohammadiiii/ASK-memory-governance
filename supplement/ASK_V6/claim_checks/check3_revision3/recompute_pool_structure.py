"""Claim check 3: pool structure of MGP-6 v4.3 public components by text hash (no text printed).
For each component: (i) the six snippets (position -> text hash) of every item; (ii) per (component, length) the indexed pair per action;
checks: pairs disjoint and covering the six-sentence pool; pool identical across lengths and actions; numbering permuted between actions."""
import sys, json, collections, importlib, hashlib
sys.dont_write_bytecode = True
sys.path.insert(0, '/tmp/ask_base_src')
m = importlib.import_module('ask.eval.mgp6_v43')
R = '/Users/alimohammadi/Workspace/research/ASK-memory-governance'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
h = lambda s: hashlib.sha256(s.encode()).hexdigest()[:12]
def snippets_of(rec):
    sn = {}
    for t in rec.dialogue:
        for o, s in m._EVIDENCE_MESSAGE_RE.findall(t['text']):
            sn[m._ORDINAL_MESSAGE_POSITIONS[o.casefold()]] = h(' '.join(s.split()))
    return sn
res = {}
for split in ('train', 'dev'):
    recs = m.load_public_records(f'{R}/benchmarks/mgp6/mgp6_v4_3/public/{split}.jsonl')
    comps = collections.defaultdict(list)
    for r in recs: comps[(r.memory_before['principal'], r.memory_before['memory_slot'], r.memory_before['standing_value'])].append(r)
    ok_part = 0; triples = 0; pool_same_across_len = 0; pool_same_all = 0; perm = 0; npos_tot = 0
    for k, rs in comps.items():
        pools = {}; bylen = collections.defaultdict(dict); poolsets = []
        for r in rs:
            sn = snippets_of(r); v = m.linked_evidence_view(r)
            idx = frozenset(sn[it['message_position']] for it in v['indexed_evidence'])
            bylen[len(r.dialogue)][r.gold_action] = (idx, sn)
            poolsets.append(frozenset(sn.values()))
        pool_same_all += len(set(poolsets)) == 1 and len(poolsets[0]) == 6
        for L, d in bylen.items():
            triples += 1
            sets = [d[a][0] for a in d]
            cover = frozenset().union(*sets)
            ok_part += (len(d) == 3 and all(len(s) == 2 for s in sets) and len(cover) == 6 and sum(len(s) for s in sets) == 6 and cover == frozenset(next(iter(d.values()))[1].values()))
        # numbering permuted between actions: position map of the same pool differs between actions at a fixed length
        for L, d in bylen.items():
            maps = [tuple(sorted(d[a][1].items())) for a in d]
            perm += len(set(maps)) > 1
    res[split] = {'components': len(comps), 'triples': triples, 'triples_with_disjoint_cover_of_pool': ok_part, 'components_with_one_six_sentence_pool_across_all_nine_items': pool_same_all,
                  'triples_where_numbering_differs_between_actions': perm}
json.dump(res, open(OUT + '/recompute_pool_structure.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
