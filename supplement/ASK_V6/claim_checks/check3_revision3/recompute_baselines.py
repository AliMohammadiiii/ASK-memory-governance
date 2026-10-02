"""Claim check 3: baseline correct counts (post and pre override) from judgments files; aggregates only, no text printed."""
import json, collections, os, hashlib
V = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs_local/lme_final_controller_v12_qwen_180'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
res = {}
for b in ('b1', 'b2', 'b3', 'b4'):
    rows = [json.loads(l) for l in open(f'{V}/{b}/judgments.jsonl')]
    orig = [json.loads(l) for l in open(f'{V}/{b}/judgments.jsonl.pre_adjudication.orig')]
    keys = collections.Counter()
    for r in rows: keys.update(k for k in r.keys())
    diff_ids = [r['session_id'] for r, o in zip(rows, orig) if r != o]
    ov = [r for r in rows if any(('adjud' in k or 'overrid' in k) and r.get(k) not in (None, False) for k in r)]
    rep = json.load(open(f'{V}/{b}/report.json')); rep0 = json.load(open(f'{V}/{b}/report.json.pre_adjudication.orig'))
    direction = collections.Counter()
    for r, o in zip(rows, orig):
        if r != o: direction[f"{bool(o['correct'])}->{bool(r['correct'])}"] += 1
    extra_keys = sorted(k for k in keys if k not in orig[0].keys())
    res[b] = {'n': len(rows), 'correct_post': sum(bool(r['correct']) for r in rows), 'correct_orig_file': sum(bool(o['correct']) for o in orig), 'rows_differing_from_orig': len(diff_ids),
              'direction': dict(direction), 'rows_with_override_fields': len(ov), 'extra_keys_vs_orig': extra_keys, 'report_overall_post': rep.get('overall_accuracy'), 'report_overall_orig': rep0.get('overall_accuracy'),
              'judge_models_used': rep.get('judge_models_used'), 'model_ids_in_judgments': dict(collections.Counter(r.get('judge_model_id') for r in rows)),
              'requested_judge': dict(collections.Counter(r.get('requested_judge_model_id') for r in rows))}
json.dump(res, open(OUT + '/recompute_baselines.json', 'w'), indent=1)
for b, r in res.items(): print(b, {k: v for k, v in r.items()})
