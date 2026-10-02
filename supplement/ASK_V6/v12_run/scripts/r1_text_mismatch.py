import json, sys, hashlib, collections, unicodedata, re, difflib
RUN = sys.argv[1]
def h(s): return hashlib.sha256(str(s).encode('utf-8')).hexdigest()[:16]
al = json.load(open('handoff/aligned_rows.json'))
final_idx = {(r['shard'], r['row_id']): r for r in al if r['proc'] == r['completing_proc']}
cache = collections.defaultdict(list)
for k in range(8):
    for l in open(f'{RUN}/controller/_shard{k}/extraction_cache.jsonl', encoding='utf-8'):
        if not l.strip(): continue
        r = json.loads(l)
        for it in (r['output'].get('items') or []):
            es = it.get('evidence_span') or {}
            cache[k].append(dict(sid=es.get('session_id'), sid_h=h(es.get('session_id')), turn=es.get('turn_idx'), text=it['text'], type=it.get('type_guess')))
log_texts = {}
for k in range(8):
    for l in open(f'{RUN}/controller/_shard{k}/action_log.jsonl', encoding='utf-8'):
        r = json.loads(l); log_texts[(k, r['id'])] = r['candidate_text']
# recompute unmatched sets per shard
out = []
cats = collections.Counter()
for k in range(8):
    cc = collections.defaultdict(list)
    for it in cache[k]: cc[(it['sid_h'], h(it['text']), it['type'])].append(it)
    fr = [(key, r) for key, r in final_idx.items() if key[0] == k]
    cl = collections.Counter((r['sid_h'], r['text_h'], r['type']) for _, r in fr)
    um_log = []; 
    seen = collections.Counter()
    for (key, r) in sorted(fr, key=lambda x: x[0][1]):
        kk = (r['sid_h'], r['text_h'], r['type'])
        seen[kk] += 1
        if seen[kk] > len(cc.get(kk, [])) and not (len(cc.get(kk, [])) >= 1 and False):
            um_log.append((key, r))
    # cache items not used
    um_cache = []
    for kk, lst in cc.items():
        if cl.get(kk, 0) < len(lst): um_cache.extend(lst[cl.get(kk, 0):])
    # match um_log to um_cache by (sid_h)
    for (key, r) in um_log:
        t = log_texts[key]
        cand = [c for c in um_cache if c['sid_h'] == r['sid_h']]
        best = None; bscore = -1
        for c in cand:
            sc = difflib.SequenceMatcher(None, t, c['text']).ratio()
            if sc > bscore: best, bscore = c, sc
        if best is None: cats['no_cache_candidate'] += 1; out.append((k, key[1], r['q'], None, 0.0)); continue
        def n1(s): return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s)).strip().casefold()
        if t == best['text']: cat = 'identical_but_count_excess'
        elif n1(t) == n1(best['text']): cat = 'whitespace_case_unicode_only'
        elif t.startswith(best['text']) or best['text'].startswith(t): cat = 'prefix_relation'
        else: cat = 'other(ratio=%.2f)' % bscore
        cats[cat] += 1
        out.append((k, key[1], r['q'], cat, round(bscore, 3), len(t), len(best['text']), r['type'], best['type'], r['sid_h']))
        um_cache.remove(best)
    cats['unmatched_cache_remaining'] += len(um_cache)
print(dict(cats))
json.dump(out, open('handoff/text_mismatch_pairs.json', 'w'))
for o in out[:30]: print(o)
