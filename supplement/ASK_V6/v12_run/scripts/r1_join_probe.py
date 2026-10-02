import json, collections
rows = json.load(open('handoff/aligned_rows.json'))
items = json.load(open('handoff/merged_cache_items.json'))
print(len(rows), len(items))
print('log types', collections.Counter(r['type'] for r in rows))
print('cache types', collections.Counter(i[3] for i in items))
stale = [r for r in rows if r['proc'] != r['completing_proc']]
final = [r for r in rows if r['proc'] == r['completing_proc']]
print('completing None', sum(r['completing_proc'] is None for r in rows))
print('final', len(final), 'stale', len(stale))
c_items = collections.Counter((i[0], i[2], i[3]) for i in items)
c_final = collections.Counter((r['sid_h'], r['text_h'], r['type']) for r in final)
c_all = collections.Counter((r['sid_h'], r['text_h'], r['type']) for r in rows)
keys = set(c_items) | set(c_final)
pos = sum(max(0, c_final[k]-c_items[k]) for k in keys); neg = sum(max(0, c_items[k]-c_final[k]) for k in keys)
print('final vs cache: positive excess', pos, 'negative', neg, 'net', pos-neg, 'F-C', len(final)-len(items))
print('log keys not in cache (final rows)', sum(v for k, v in c_final.items() if k not in c_items), 'cache items keys not in final log', sum(v for k, v in c_items.items() if k not in c_final))
print('log keys not in cache (all rows)', sum(v for k, v in c_all.items() if k not in c_items))
# question-level
qs = collections.Counter((r['shard'], r['q']) for r in final)
print('questions with final rows', len(qs), 'stale-only questions', len({(r['shard'], r['q']) for r in stale} - set(qs)))
