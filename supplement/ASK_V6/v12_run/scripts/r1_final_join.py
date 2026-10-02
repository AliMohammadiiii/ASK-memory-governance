#!/usr/bin/env python3
"""Final-run rows versus cache items with a session-id-free key (text hash, type) per shard; reuse analysis. Counts only."""
import json, sys, hashlib, collections
RUN = sys.argv[1]
def h(s): return hashlib.sha256(str(s).encode('utf-8')).hexdigest()[:16]
al = json.load(open('handoff/aligned_rows.json'))
fin = [r for r in al if r['proc'] == r['completing_proc']]
res = {}
mq_rows = 0; mq_keys = 0; mq_sessions = set(); mq_questions = set(); mq_turnkeys = set(); mq_shards = collections.Counter()
for k in range(8):
    citems = []
    for l in open(f'{RUN}/controller/_shard{k}/extraction_cache.jsonl', encoding='utf-8'):
        if not l.strip(): continue
        r = json.loads(l)
        for it in (r['output'].get('items') or []):
            es = it.get('evidence_span') or {}
            citems.append((h(it['text']), it.get('type_guess'), r['key'], es.get('turn_idx'), h(es.get('session_id'))))
    cc = collections.Counter((a, b) for a, b, *_ in citems)
    fr = [r for r in fin if r['shard'] == k]
    cl = collections.Counter((r['text_h'], r['type']) for r in fr)
    q_by_key = collections.defaultdict(set); s_by_key = collections.defaultdict(set)
    for r in fr:
        q_by_key[(r['text_h'], r['type'])].add(r['q']); s_by_key[(r['text_h'], r['type'])].add(r['sid_h'])
    pos = neg = 0
    for key in set(cc) | set(cl):
        d = cl[key] - cc[key]
        if d > 0:
            pos += d
            if len(q_by_key[key]) >= 2:
                mq_rows += d; mq_keys += 1; mq_questions |= {(k, q) for q in q_by_key[key]}; mq_sessions |= {(k, s) for s in s_by_key[key]}; mq_shards[k] += d
                for it in citems:
                    if (it[0], it[1]) == key: mq_turnkeys.add((k, it[2]))
        elif d < 0: neg += -d
    res[k] = dict(final_rows=len(fr), cache_items=len(citems), pos=pos, neg=neg)
print(res)
print('sum pos', sum(v['pos'] for v in res.values()), 'sum neg', sum(v['neg'] for v in res.values()))
print('multi-question excess rows', mq_rows, 'keys', mq_keys, 'sessions', len(mq_sessions), 'questions', len(mq_questions), 'distinct cache keys (turn extractions) behind them', len(mq_turnkeys), dict(mq_shards))
