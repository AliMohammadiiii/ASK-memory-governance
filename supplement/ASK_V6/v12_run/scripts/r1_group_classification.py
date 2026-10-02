#!/usr/bin/env python3
"""Classify (a) the 88 repeated (session, candidate_id) pairs and (b) the 1,277 (session, text, type) groups with >1 decision
by the mechanism that produced the repetition. Uses aligned rows (ids/hashes only)."""
import json, sys, hashlib, collections
RUN = sys.argv[1]
al = json.load(open('handoff/aligned_rows.json'))
# merged order check
cat = hashlib.sha256()
for k in range(8): cat.update(open(f'{RUN}/controller/_shard{k}/action_log.jsonl', 'rb').read())
top = hashlib.sha256(open(f'{RUN}/controller/action_log.jsonl', 'rb').read()).hexdigest()
print('top-level action_log == concatenation of shard logs 0..7:', cat.hexdigest() == top)
for r in al: r['status'] = 'final' if r['proc'] == r['completing_proc'] else 'stale'
# (a) (session, candidate_id) pairs
by = collections.defaultdict(list)
for r in al: by[(r['sid_h'], r['cand_id'])].append(r)
dups = {k: v for k, v in by.items() if len(v) > 1}
print('dup (session,cand_id) pairs', len(dups), 'rows in them', sum(len(v) for v in dups.values()))
cl = collections.Counter()
for k, v in dups.items():
    shards = {x['shard'] for x in v}; sts = tuple(sorted(x['status'] for x in v)); qs = {(x['shard'], x['q']) for x in v}
    cl[('same_shard' if len(shards) == 1 else 'cross_shard', sts, 'same_q' if len(qs) == 1 else 'diff_q')] += 1
for k, v in cl.items(): print('  ', k, v)
# (b) groups
g = collections.defaultdict(list)
for r in al: g[(r['sid_h'], r['text_h'], r['type'])].append(r)
multi = {k: v for k, v in g.items() if len(v) > 1}
print('groups with >1 decision', len(multi), 'rows', sum(len(v) for v in multi.values()))
cls = collections.Counter(); diffact = collections.Counter()
for k, v in multi.items():
    has_stale = any(x['status'] == 'stale' for x in v)
    fin = [x for x in v if x['status'] == 'final']
    fq = collections.Counter((x['shard'], x['q']) for x in fin)
    multi_q = len(fq) >= 2
    intra_q = any(c >= 2 for c in fq.values())
    flags = tuple(n for n, f in (('stale_replay', has_stale), ('multi_question_final', multi_q), ('intra_question_repeat', intra_q)) if f)
    cls[flags] += 1
    if len({x['action'] for x in v}) > 1:
        diffact[flags] += 1
for k, v in sorted(cls.items(), key=lambda t: -t[1]): print('  group-flags', k, v, 'with_different_actions', diffact.get(k, 0))
print('groups with different actions', sum(diffact.values()))
json.dump({'dup_cand_pairs': len(dups), 'dup_pair_classes': {str(k): v for k, v in cl.items()}, 'multi_groups': len(multi), 'group_classes': {str(k): v for k, v in cls.items()}, 'group_diff_action': {str(k): v for k, v in diffact.items()}}, open('handoff/group_classification.json', 'w'), indent=1)
