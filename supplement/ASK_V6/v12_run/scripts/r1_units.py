#!/usr/bin/env python3
"""Count extraction-trace rows, cache entries and extracted items per shard and in the merged files, in comparable units.
Only counts and hashes are written. Usage: r1_units.py RUN_DIR"""
import json, sys, hashlib, collections
RUN = sys.argv[1]
def h(s): return hashlib.sha256(str(s).encode('utf-8')).hexdigest()[:16]
def jl(p):
    with open(p, encoding='utf-8') as f:
        for l in f:
            if l.strip(): yield json.loads(l)
def turn_from_prompt(prompt):
    m = "Current turn:\n"; s = prompt.find(m)
    if s < 0: return None
    s += len(m); e = prompt.find("\n\nNext turn:", s)
    if e < 0: return None
    try: return json.loads(prompt[s:e].strip())
    except Exception: return None
res = {}
items_by_source = {}
trace_keys = {}
for tag, tp, cp in [('merged', f'{RUN}/controller/extraction_trace.jsonl', f'{RUN}/controller/extraction_cache.jsonl')] + \
        [(f's{k}', f'{RUN}/controller/_shard{k}/extraction_trace.jsonl', f'{RUN}/controller/_shard{k}/extraction_cache.jsonl') for k in range(8)]:
    tr_rows = 0; tr_items = 0; tkeys = []; parse_fail = 0
    for r in jl(tp):
        tr_rows += 1
        vo = r.get('validated_output') or {}
        n = len(vo.get('items') or []); tr_items += n
        t = turn_from_prompt(r.get('prompt', ''))
        if t is None: parse_fail += 1; tkeys.append(None); continue
        tkeys.append((h(t.get('session_id')), t.get('turn_idx'), h(t.get('content')), n))
    c_rows = 0; c_items = 0; ckeys = []
    citems = []
    for r in jl(cp):
        c_rows += 1; its = (r.get('output') or {}).get('items') or []
        c_items += len(its); ckeys.append(r['key'])
        for it in its:
            es = it.get('evidence_span') or {}
            citems.append((h(es.get('session_id')), es.get('turn_idx'), h(it.get('text')), it.get('type_guess')))
    res[tag] = dict(trace_rows=tr_rows, trace_items=tr_items, trace_parse_fail=parse_fail,
                    trace_distinct_turn_keys=len({(a, b, c) for (a, b, c, d) in [x for x in tkeys if x]}),
                    cache_entries=c_rows, cache_distinct_keys=len(set(ckeys)), cache_items=c_items,
                    cache_distinct_items=len(set(citems)))
    if tag == 'merged':
        trace_keys['merged'] = tkeys
        items_by_source['merged'] = citems
json.dump(res, open('handoff/units_counts.json', 'w'), indent=1)
json.dump(items_by_source['merged'], open('handoff/merged_cache_items.json', 'w'))
json.dump(trace_keys['merged'], open('handoff/merged_trace_turnkeys.json', 'w'))
for t, v in res.items(): print(t, v)
print('sum of shard trace rows', sum(res[f's{k}']['trace_rows'] for k in range(8)), 'sum shard cache entries', sum(res[f's{k}']['cache_entries'] for k in range(8)), 'sum shard cache items', sum(res[f's{k}']['cache_items'] for k in range(8)), 'sum shard trace items', sum(res[f's{k}']['trace_items'] for k in range(8)))
