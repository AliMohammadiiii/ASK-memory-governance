import json, sys, hashlib, collections, unicodedata, re, difflib
RUN = sys.argv[1]
def h(s): return hashlib.sha256(str(s).encode('utf-8')).hexdigest()[:16]
def n1(s): return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s)).strip().casefold()
al = json.load(open('handoff/aligned_rows.json'))
fin = [r for r in al if r['proc'] == r['completing_proc']]
log_text = {}
for k in range(8):
    for l in open(f'{RUN}/controller/_shard{k}/action_log.jsonl', encoding='utf-8'):
        r = json.loads(l); log_text[(k, r['id'])] = (r['candidate_text'], r['session_id'])
UL = []; UC = []
for k in range(8):
    items = []
    for l in open(f'{RUN}/controller/_shard{k}/extraction_cache.jsonl', encoding='utf-8'):
        if not l.strip(): continue
        r = json.loads(l)
        for it in (r['output'].get('items') or []):
            es = it.get('evidence_span') or {}
            items.append((h(es.get('session_id')), h(it['text']), it.get('type_guess'), it['text'], es.get('session_id'), es.get('turn_idx')))
    ck = set((a, b, c) for a, b, c, *_ in items)
    lk = set((r['sid_h'], r['text_h'], r['type']) for r in fin if r['shard'] == k)
    for r in fin:
        if r['shard'] == k and (r['sid_h'], r['text_h'], r['type']) not in ck: UL.append((k, r))
    for it in items:
        if (it[0], it[1], it[2]) not in lk: UC.append((k, it))
print('UL', len(UL), 'UC', len(UC))
cats = collections.Counter(); used = set()
for k, r in UL:
    t, sid = log_text[(k, r['row_id'])]
    best = None; bs = -1
    for j, (kc, it) in enumerate(UC):
        if kc != k or j in used: continue
        sc = difflib.SequenceMatcher(None, t, it[3]).ratio()
        if sc > bs: bs, best = sc, j
    if best is None: cats['no_partner'] += 1; continue
    used.add(best); it = UC[best][1]
    same_sid = (it[4] == sid); same_type = (it[2] == r['type'])
    if t == it[3]: c = 'identical_text'
    elif n1(t) == n1(it[3]): c = 'ws_case_unicode_only'
    elif t.startswith(it[3]) or it[3].startswith(t): c = 'prefix'
    else: c = 'other'
    cats[(c, 'same_sid' if same_sid else 'diff_sid', 'same_type' if same_type else 'diff_type', 'ratio>=0.9' if bs >= .9 else 'ratio<0.9')] += 1
for kk, v in cats.items(): print(kk, v)
print('UC unused', len(UC) - len(used))
