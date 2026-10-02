import json, sys, collections, hashlib
D = sys.argv[1]
tot = 0
for s in range(8):
    rows = [json.loads(l) for l in open(f'{D}/controller/_shard{s}/action_log.jsonl', encoding='utf-8') if l.strip()]
    ids = [r['id'] for r in rows]; cids = [r['candidate_id'] for r in rows]
    ts = [r['timestamp'] for r in rows]
    id_gaps = sum(1 for a, b in zip(ids, ids[1:]) if b != a + 1)
    id_dups = len(ids) - len(set(ids))
    cid_dec = [i for i, (a, b) in enumerate(zip(cids, cids[1:]), 1) if b < a]
    cid_nonmono = sum(1 for a, b in zip(cids, cids[1:]) if b != a + 1)
    ts_dec = sum(1 for a, b in zip(ts, ts[1:]) if b < a)
    print(f's{s}: rows={len(rows)} id[{min(ids)}..{max(ids)}] id_gaps={id_gaps} id_dups={id_dups} cid[{min(cids)}..{max(cids)}] cid_decreases_at={cid_dec[:10]} cid_not_plus1={cid_nonmono} ts_decreases={ts_dec} t0={ts[0][:19]} t1={ts[-1][:19]} nsess={len({r["session_id"] for r in rows})}')
    tot += len(rows)
print('total', tot)
top = sum(1 for l in open(f'{D}/controller/action_log.jsonl', encoding='utf-8') if l.strip())
print('top-level', top)
