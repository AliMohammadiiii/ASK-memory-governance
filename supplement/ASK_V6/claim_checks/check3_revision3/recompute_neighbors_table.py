"""Claim check 3: re-derive Table (neighbors) marks from FUNCTIONAL_EQUIVALENCE_MATRIX.csv with the rule stated in the caption,
and check the 'twelve closest' selection. Uses only the supplied coding matrix (no new literature work)."""
import csv, re, json, collections
S = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/ASK_supplement/related_work/'
D = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3/'
rows = list(csv.DictReader(open(S + 'FUNCTIONAL_EQUIVALENCE_MATRIX.csv', newline='', encoding='utf-8-sig')))
ask = rows[0]; comp = rows[1:]
feat = [f'F{i:02d}' for i in range(1, 36)]
ask2 = [f for f in feat if ask[f] == '2']
res = {'ask_n_at_2': len(ask2), 'ask_col': ask['n_ASK2_features_at_2']}
cnt = {}
for r in comp:
    n = sum(r[f] == '2' for f in ask2); cnt[r['short_name']] = (n, int(r['n_ASK2_features_at_2']))
res['count_recomputed_vs_column_mismatch'] = {k: v for k, v in cnt.items() if v[0] != v[1]}
rank = sorted(comp, key=lambda r: -int(r['n_ASK2_features_at_2']))
res['ranking_top15'] = [(r['short_name'], int(r['n_ASK2_features_at_2'])) for r in rank[:16]]
cols = {'Abstain': ['F06'], 'Lineage': ['F05', 'F13', 'F14'], 'Typed': ['F11', 'F12'], 'Log': ['F18'], 'Replay': ['F23', 'F24'], 'ActionEval': ['F25']}
def mark(codes):
    known = [c for c in codes if c != 'U']
    if not known: return 'not stated'
    if all(c == '2' for c in codes): return 'yes'
    if all(c == '0' for c in known) and len(known) == len(codes): return 'no'
    if all(c == '0' for c in known): return 'no'
    return 'partial'
name = {'GPM': 'GPM', 'MemTX': 'MemTX', 'TARL': 'TARL', 'Persona': 'Persona', 'TOKI': 'TOKI', 'Quipu': 'Quipu', 'MemGuard (verifier)': 'MemGuard-verifier', 'ECHO': 'ECHO', 'STALE/CUPMEM': 'STALE', 'SodaMem': 'SodaMem', 'Eywa': 'Eywa', 'Graph-native memory': 'GraphNativeBeliefRevision'}
tex = open(D + 'sections/02_related_work.tex').read()
tab = {}
for line in tex.splitlines():
    m = re.match(r'^(GPM|MemTX|TARL|Persona|TOKI|Quipu|MemGuard \(verifier\)|ECHO|STALE/CUPMEM|SodaMem|Eywa|Graph-native memory)~\\citep\{[^}]*\} & (.*) \\\\$', line)
    if m: tab[m.group(1)] = [x.strip() for x in m.group(2).split('&')]
by = {r['short_name']: r for r in comp}
mism = []; ncell = 0
for pn, mn in name.items():
    r = by[mn]
    mine = [mark([r[f] for f in fs]) for fs in cols.values()]
    for c, a, b in zip(cols, tab[pn], mine):
        ncell += 1
        if a != b: mism.append((pn, c, a, b, [r[f] for f in cols[c]]))
res['table_cells_checked'] = ncell; res['table_rows_parsed'] = len(tab); res['cell_mismatches'] = mism
res['selected12_in_top12_by_count'] = sorted(set(name.values())) == sorted(r['short_name'] for r in rank[:12])
res['selected12_counts'] = {k: cnt[k] for k in name.values()}
res['classification_counts'] = dict(collections.Counter(r['classification'] for r in comp))
json.dump(res, open(OUT + 'recompute_neighbors_table.json', 'w'), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
