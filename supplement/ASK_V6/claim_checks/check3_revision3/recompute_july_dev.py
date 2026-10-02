"""Claim check 3: re-parse stored replies of the July development run directories under both repository parsers. Aggregates only."""
import sys, json, os, collections, importlib
sys.dont_write_bytecode = True
B = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs/mgp6_v43/dev'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
def load(root):
    for k in [k for k in sys.modules if k == 'ask' or k.startswith('ask.')]: del sys.modules[k]
    sys.path.insert(0, root); m = importlib.import_module('ask.eval.mgp6_v43'); sys.path.remove(root); return m
base = load('/tmp/ask_base_src'); bp = base.parse_action_response
wt = load('/tmp/ask_wt_src'); wp = wt.parse_action_response
def tryp(f, s):
    try: return f(s)
    except Exception as e: return None
res = {}
for d in sorted(x for x in os.listdir(B) if os.path.isdir(os.path.join(B, x))):
    rows = [json.loads(l) for l in open(os.path.join(B, d, 'raw_responses.jsonl'))]
    ids = {r['public_id'] for r in rows}
    s = [tryp(bp, r['raw_response']) for r in rows]; t = [tryp(wp, r['raw_response']) for r in rows]
    models = collections.Counter(str(r.get('model_id') or r.get('model') or r.get('system')) for r in rows)
    res[d] = {'n': len(rows), 'n_ids': len(ids), 'strict_invalid': sum(x is None for x in s), 'tolerant_invalid': sum(x is None for x in t),
              'fenced': sum('```' in r['raw_response'] for r in rows), 'strict_ne_tolerant': sum(a != b for a, b in zip(s, t)),
              'max_len': max(len(r['raw_response']) for r in rows), 'model_or_system': dict(models),
              'has_model_field': 'model_id' in rows[0], 'fallback_used': sum(bool(r.get('fallback_used')) for r in rows), 'finish_reasons': dict(collections.Counter(r.get('finish_reason') for r in rows))}
json.dump(res, open(OUT + '/recompute_july_dev.json', 'w'), indent=1)
for d, r in res.items(): print(d, {k: v for k, v in r.items() if k not in ('finish_reasons',)}, r['finish_reasons'])
print('dirs', len(res), 'model dirs', sum(r['has_model_field'] for r in res.values()))
