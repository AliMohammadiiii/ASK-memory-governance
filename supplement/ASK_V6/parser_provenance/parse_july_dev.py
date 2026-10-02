"""Parser identity check for the July manuscript-model development runs (public development items only).
usage: parse_july_dev.py <src dir containing ask/> <out.json> ; reads raw_responses.jsonl of every dev run directory and parses each stored reply."""
import sys, json, glob, os, hashlib
src, out = sys.argv[1], sys.argv[2]
sys.dont_write_bytecode = True; sys.path.insert(0, src)
import ask.eval.mgp6_v43 as m
assert m.__file__.startswith(src)
D = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs/mgp6_v43/dev'
res = {}
for d in sorted(glob.glob(D + '/*/')):
    rr = d + 'raw_responses.jsonl'
    if not os.path.exists(rr): continue
    rows = [json.loads(l) for l in open(rr, encoding='utf-8') if l.strip()]
    cnt = {'n': len(rows), 'strict_or_module_valid': 0, 'invalid': 0, 'fenced': 0, 'nonstring': 0}
    for r in rows:
        txt = None
        for k in ('raw_response', 'response', 'raw', 'text', 'output'):
            if isinstance(r.get(k), str): txt = r[k]; break
        if txt is None: cnt['nonstring'] += 1; continue
        if txt.strip().startswith('```'): cnt['fenced'] += 1
        try: m.parse_action_response(txt); cnt['strict_or_module_valid'] += 1
        except Exception: cnt['invalid'] += 1
    res[os.path.basename(d.rstrip('/'))] = cnt
json.dump({'module_sha256': hashlib.sha256(open(m.__file__, 'rb').read()).hexdigest(), 'runs': res}, open(out, 'w'), indent=1)
print(src)
for k, v in res.items(): print(' ', k, v)
