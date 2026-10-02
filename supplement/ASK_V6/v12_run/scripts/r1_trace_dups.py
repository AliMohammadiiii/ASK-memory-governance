#!/usr/bin/env python3
"""Duplicate (session, turn_idx, content) rows within each shard's extraction trace: flags only, no text."""
import json, sys, hashlib, collections
RUN = sys.argv[1]
def h(s): return hashlib.sha256(str(s).encode('utf-8')).hexdigest()[:12]
def turn_from_prompt(prompt):
    m = "Current turn:\n"; s = prompt.find(m)
    if s < 0: return None
    s += len(m); e = prompt.find("\n\nNext turn:", s)
    try: return json.loads(prompt[s:e].strip())
    except Exception: return None
rows_out = []
for k in range(8):
    seen = collections.defaultdict(list)
    for pos, l in enumerate(open(f'{RUN}/controller/_shard{k}/extraction_trace.jsonl', encoding='utf-8')):
        if not l.strip(): continue
        r = json.loads(l); t = turn_from_prompt(r['prompt'])
        key = (t.get('session_id'), t.get('turn_idx'), t.get('content'), t.get('timestamp'))
        resp = r.get('responses') or []
        md = (resp[0].get('metadata') if resp else {}) or {}
        seen[key].append(dict(pos=pos, n_items=len((r.get('validated_output') or {}).get('items') or []), parse_path=r.get('parse_path'), repair_used=r.get('repair_used'), first_parse_error=r.get('first_parse_error') is not None,
            n_resp=len(resp), valid_json=md.get('valid_json'), schema_pass=md.get('schema_pass'), task_pass=md.get('task_pass'), finish=md.get('finish_reason'), attempt_index=md.get('attempt_index'), fallback_used=md.get('fallback_used'),
            cover_flag=('could not be parsed' in ((r.get('validated_output') or {}).get('coverage_note') or '').casefold()), resp_hash=md.get('raw_response_hash')))
    for key, lst in seen.items():
        if len(lst) > 1:
            rows_out.append(dict(shard=k, sid_h=h(key[0]), turn=key[1], n=len(lst), same_resp_hash=len({x['resp_hash'] for x in lst}) == 1, rows=[{kk: vv for kk, vv in x.items() if kk != 'resp_hash'} for x in lst]))
print('dup groups', len(rows_out), 'extra rows', sum(x['n'] - 1 for x in rows_out))
for x in rows_out: print(x['shard'], x['sid_h'], x['turn'], x['n'], 'same_resp_hash', x['same_resp_hash'], [(r['pos'], r['n_items'], r['parse_path'], r['repair_used'], r['first_parse_error'], r['valid_json'], r['schema_pass'], r['task_pass'], r['finish'], r['cover_flag']) for r in x['rows']])
json.dump(rows_out, open('handoff/trace_dups.json', 'w'))
