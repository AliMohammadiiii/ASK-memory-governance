import json, sys, hashlib, collections, unicodedata, re
RUN = sys.argv[1]
def h(s): return hashlib.sha256(str(s).encode('utf-8')).hexdigest()[:16]
rows = json.load(open('handoff/aligned_rows.json'))
final = [r for r in rows if r['proc'] == r['completing_proc']]
# per-shard cache items with texts held in memory only
cache_items = collections.defaultdict(list)   # shard -> list of (sid_h, text_h, type, turn_idx, text)
for k in range(8):
    for l in open(f'{RUN}/controller/_shard{k}/extraction_cache.jsonl', encoding='utf-8'):
        if not l.strip(): continue
        r = json.loads(l)
        for it in (r['output'].get('items') or []):
            es = it.get('evidence_span') or {}
            cache_items[k].append((h(es.get('session_id')), h(it['text']), it.get('type_guess'), es.get('turn_idx'), it['text'], r['key']))
# per shard counts
stat = collections.Counter(); detail = []
for k in range(8):
    cc = collections.Counter((a, b, c) for (a, b, c, d, e, f) in cache_items[k])
    fr = [r for r in final if r['shard'] == k]
    cl = collections.Counter((r['sid_h'], r['text_h'], r['type']) for r in fr)
    qs = collections.defaultdict(set)
    for r in fr: qs[(r['sid_h'], r['text_h'], r['type'])].add(r['q'])
    for key in set(cc) | set(cl):
        a, b = cl[key], cc[key]
        nq = len(qs.get(key, ()))
        if a == b: stat['balanced_rows'] += a
        elif a > b:
            stat['pos_excess_rows'] += a - b
            stat['pos_excess_keys'] += 1
            stat['pos_multiq_rows' if nq >= 2 else 'pos_singleq_rows'] += a - b
            if b == 0: stat['pos_notincache_rows'] += a
        else:
            stat['neg_excess_rows'] += b - a; stat['neg_keys'] += 1
            if a == 0: stat['neg_notinlog_rows'] += b
print(dict(stat))
