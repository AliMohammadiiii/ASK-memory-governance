"""Re-derive actions from the stored raw reply of every Phase 13/16 result row with one named parser module.
usage: parse_rows_with_module.py <srcdir containing ask/> <out.json>
Only the stored reply text (first 120 characters of the model output) is parsed; no benchmark text is read."""
import sys, json, glob, os
src, out = sys.argv[1], sys.argv[2]
sys.dont_write_bytecode = True
sys.path.insert(0, src)
import ask.eval.mgp6_v43 as m
assert m.__file__.startswith(src), m.__file__
DIRS = ['../phase13_routing_check', 'out_ag_gemini-3.8-flash-medium', 'out_ag_gemini-3.8-flash-high', 'out_ocg_glm-5.3-flash', 'out_ag_gpt-oss-120b-medium']
res = {}
for d in DIRS:
    lat = {}
    for l in open(d + '/results.jsonl', encoding='utf-8'):
        if l.strip():
            j = json.loads(l); lat[(j['public_id'], j['cell'], j['repeat'])] = j
    rows = []
    for (pid, cell, rep), j in sorted(lat.items()):
        raw = j.get('raw') or ''
        try: act = m.parse_action_response(raw)
        except Exception: act = None
        rows.append([pid, cell, rep, act, len(raw), j.get('action')])
    res[d] = rows
json.dump({'module': src, 'module_sha256': __import__('hashlib').sha256(open(m.__file__, 'rb').read()).hexdigest(), 'rows': res}, open(out, 'w'))
print(src, {d: len(r) for d, r in res.items()})
