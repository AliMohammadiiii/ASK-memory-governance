"""Claim check 3: accuracy and macro-F1 of the July development prediction files against public dev gold (Table tab:dev)."""
import json, os, collections
B = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs/mgp6_v43/dev'
R = '/Users/alimohammadi/Workspace/research/ASK-memory-governance'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
gold = {}
for l in open(R + '/benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl'):
    r = json.loads(l); gold[r['public_id']] = r['gold_action']
ACT = ['KEEP', 'SUPERSEDE', 'ABSTAIN']
def mf1(pairs):
    f = []
    for c in ACT:
        tp = sum(1 for g, p in pairs if g == c and p == c); fp = sum(1 for g, p in pairs if g != c and p == c); fn = sum(1 for g, p in pairs if g == c and p != c)
        pr = tp / (tp + fp) if tp + fp else 0; rc = tp / (tp + fn) if tp + fn else 0
        f.append(2 * pr * rc / (pr + rc) if pr + rc else 0)
    return sum(f) / 3
res = {}
for d in sorted(x for x in os.listdir(B) if os.path.isdir(os.path.join(B, x))):
    rows = [json.loads(l) for l in open(os.path.join(B, d, 'predictions.jsonl'))]
    pairs = [(gold[r['public_id']], r['action']) for r in rows]
    res[d] = {'n': len(rows), 'acc': round(sum(g == p for g, p in pairs) / len(pairs), 4), 'macro_f1': round(mf1(pairs), 4), 'gold_counts': dict(collections.Counter(g for g, _ in pairs))}
json.dump(res, open(OUT + '/recompute_dev_table.json', 'w'), indent=1)
for d, r in res.items(): print(d, r['n'], r['acc'], r['macro_f1'])
print(collections.Counter(gold.values()))
