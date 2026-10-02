"""Claim check 3: decision-log accounting of the merged V12 action log. Counts only; candidate text is hashed in memory for matching and never printed."""
import json, csv, collections, hashlib
V = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs_local/lme_final_controller_v12_qwen_180/controller/action_log.jsonl'
STALE = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/ASK_supplement/v12_run/SURPLUS_883_STALE_ROWS_822.csv'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
raw = open(V, 'rb').read(); sha = hashlib.sha256(raw).hexdigest()
rows = [json.loads(l) for l in raw.decode().splitlines() if l.strip()]
stale = list(csv.DictReader(open(STALE, newline='')))
ts_count = collections.Counter(r['timestamp'] for r in rows)
stale_ts = {s['timestamp_utc'] for s in stale}
stale_ts_in_log = [r for r in rows if r['timestamp'] in stale_ts]
dup_ts_among_stale = sum(ts_count[t] > 1 for t in stale_ts)
# text-hash cross check of matched rows
sh = collections.defaultdict(list)
for r in rows: sh[r['timestamp']].append(r)
text_ok = 0
for s in stale:
    cands = sh.get(s['timestamp_utc'], [])
    if len(cands) == 1 and hashlib.sha256(cands[0]['candidate_text'].encode()).hexdigest()[:16] == s['candidate_text_sha256_16'] and cands[0]['action'] == s['action'] and cands[0]['candidate_type'] == s['candidate_type']: text_ok += 1
is_stale = lambda r: r['timestamp'] in stale_ts
comp = [r for r in rows if not is_stale(r)]; st = [r for r in rows if is_stale(r)]
def summ(rs):
    a = collections.Counter(r['action'] for r in rs); t = collections.Counter(r['candidate_type'] for r in rs)
    keep = [r for r in rs if r['action'] == 'Keep']; sup = [r for r in rs if r['action'] == 'Supersede']; ab = [r for r in rs if r['action'] == 'Abstain']
    return {'rows': len(rs), 'actions': dict(a), 'types': dict(t), 'sessions_distinct': len({r['session_id'] for r in rs}),
            'keep_with_resulting_id': sum(r['resulting_memory_id'] is not None for r in keep), 'keep_total': len(keep),
            'supersede_with_prior_and_resulting': sum(r['prior_memory_id'] is not None and r['resulting_memory_id'] is not None for r in sup), 'supersede_total': len(sup),
            'abstain_with_resulting_id': sum(r['resulting_memory_id'] is not None for r in ab), 'abstain_total': len(ab),
            'abstain_with_prior_id': sum(r['prior_memory_id'] is not None for r in ab)}
res = {'log_sha256': sha, 'rows_all': len(rows), 'distinct_timestamps': len(ts_count), 'stale_csv_rows': len(stale), 'stale_matched_unique_by_timestamp': len(stale_ts_in_log), 'stale_ts_duplicated_in_log': dup_ts_among_stale,
       'stale_text_action_type_hash_match': text_ok, 'all': summ(rows), 'completed': summ(comp), 'stale': summ(st),
       'pct_stale': round(100 * len(st) / len(rows), 2), 'keep_share_completed': round(summ(comp)['actions']['Keep'] / len(comp), 4), 'sup_share_completed': round(summ(comp)['actions']['Supersede'] / len(comp), 4), 'abs_share_completed': round(summ(comp)['actions']['Abstain'] / len(comp), 4)}
json.dump(res, open(OUT + '/recompute_v12_log_accounting.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
