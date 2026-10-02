"""Claim check 3: the directories that appear to be the source of Table tab:dev (the later complete development rerun):
accuracy, macro-F1 and parsing of stored replies, aggregates only."""
import sys, json, os, collections, importlib
sys.dont_write_bytecode = True
BK = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs/benchmark_suite/v43_public_dev_complete_qwen35_9b/mgp6_v43_public_dev'
R = '/Users/alimohammadi/Workspace/research/ASK-memory-governance'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
def load(root):
    for k in [k for k in sys.modules if k == 'ask' or k.startswith('ask.')]: del sys.modules[k]
    sys.path.insert(0, root); m = importlib.import_module('ask.eval.mgp6_v43'); sys.path.remove(root); return m
base = load('/tmp/ask_base_src'); bp = base.parse_action_response
wt = load('/tmp/ask_wt_src'); wp = wt.parse_action_response
def tryp(f, s):
    try: return f(s)
    except Exception: return None
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
for d in sorted(os.listdir(BK)):
    p = os.path.join(BK, d)
    if not os.path.isdir(p): continue
    pf = os.path.join(p, 'predictions.jsonl'); rf = os.path.join(p, 'raw_responses.jsonl')
    if not os.path.exists(pf): res[d] = {'files': sorted(os.listdir(p))}; continue
    preds = [json.loads(l) for l in open(pf)]
    pairs = [(gold[r['public_id']], r['action']) for r in preds]
    e = {'n': len(preds), 'acc': round(sum(g == q for g, q in pairs) / len(pairs), 4), 'macro_f1': round(mf1(pairs), 4)}
    if os.path.exists(rf):
        rows = [json.loads(l) for l in open(rf)]
        s = [tryp(bp, r['raw_response']) for r in rows]; t = [tryp(wp, r['raw_response']) for r in rows]
        e.update({'raw_n': len(rows), 'strict_invalid': sum(x is None for x in s), 'tolerant_invalid': sum(x is None for x in t), 'fenced': sum('```' in r['raw_response'] for r in rows), 'strict_ne_tolerant': sum(a != b for a, b in zip(s, t)),
                  'models': dict(collections.Counter(str(r.get('model_id') or r.get('model') or r.get('system')) for r in rows))})
    res[d] = e
json.dump(res, open(OUT + '/recompute_dev_complete_rerun.json', 'w'), indent=1)
for d, r in res.items(): print(d, r)
