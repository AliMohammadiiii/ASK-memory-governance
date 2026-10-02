"""Claim check 3: each stale group (from the supplement list, matched by timestamp) should equal, in order, a contiguous run of rows
in the completed part of the log (same candidate text hash, type, action, session hash). Counts only."""
import json, csv, collections, hashlib
V = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs_local/lme_final_controller_v12_qwen_180/controller/action_log.jsonl'
STALE = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/ASK_supplement/v12_run/SURPLUS_883_STALE_ROWS_822.csv'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
h = lambda s: hashlib.sha256(s.encode()).hexdigest()[:16]
rows = [json.loads(l) for l in open(V) if l.strip()]
stale = list(csv.DictReader(open(STALE, newline='')))
stale_ts = {s['timestamp_utc'] for s in stale}
sig = lambda r: (h(r['candidate_text']), r['candidate_type'], r['action'], h(r['session_id']))
comp = [r for r in rows if r['timestamp'] not in stale_ts]
comp_sig = [sig(r) for r in comp]
groups = collections.OrderedDict()
by_ts = {r['timestamp']: r for r in rows}
for s in sorted(stale, key=lambda s: s['timestamp_utc']):
    groups.setdefault((s['shard'], s['question_id'], s['worker']), []).append(by_ts[s['timestamp_utc']])
res = {'n_groups': len(groups), 'group_sizes': [len(g) for g in groups.values()], 'matches': []}
# index completed signatures by first element
idx = collections.defaultdict(list)
for i, sg in enumerate(comp_sig): idx[sg].append(i)
exact = 0; unique = 0; rows_matched = 0
for k, g in groups.items():
    gs = [sig(r) for r in g]
    starts = [i for i in idx[gs[0]] if comp_sig[i:i + len(gs)] == gs]
    res['matches'].append({'shard': k[0], 'n': len(g), 'n_matching_starts': len(starts)})
    exact += len(starts) >= 1; unique += len(starts) == 1; rows_matched += len(g) if starts else 0
res.update({'groups_with_contiguous_match': exact, 'groups_with_unique_match': unique, 'rows_in_matched_groups': rows_matched, 'stale_rows': len(stale)})
json.dump(res, open(OUT + '/recompute_stale_prefix.json', 'w'), indent=1)
print({k: v for k, v in res.items() if k != 'matches'})
