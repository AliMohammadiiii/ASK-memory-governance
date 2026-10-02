"""Claim check 3: V12 controller grader composition and adjudication counts. Aggregates only; no benchmark text is read into output."""
import json, collections, math
V = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs_local/lme_final_controller_v12_qwen_180/controller'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
rows = [json.loads(l) for l in open(V + '/judgments.jsonl')]
def pre(r): return bool(r['correct']) if not r.get('adjudicated') else bool(r['correct_pre_adjudication'])
def src(r):
    if not r['judge_was_called']: return 'guard'
    if r['used_scoring_fallback']: return 'fallback'
    return 'model_judge'
res = {'n': len(rows), 'post_correct': sum(bool(r['correct']) for r in rows), 'pre_correct': sum(pre(r) for r in rows)}
res['pre_by_source'] = {s: {'n': sum(src(r) == s for r in rows), 'correct': sum(src(r) == s and pre(r) for r in rows)} for s in ('model_judge', 'guard', 'fallback')}
res['judge_called'] = sum(bool(r['judge_was_called']) for r in rows)
res['guards_incorrect_pre'] = sum(src(r) == 'guard' and not pre(r) for r in rows)
adj = [r for r in rows if r.get('adjudicated')]
res['adjudicated'] = {'n': len(adj), 'by_competency': dict(collections.Counter(r['competency'] for r in adj)), 'by_source': dict(collections.Counter(src(r) for r in adj)),
                      'type': dict(collections.Counter(r['adjudication_type'] for r in adj)), 'direction_incorrect_to_correct': sum((not r['correct_pre_adjudication']) and r['correct'] for r in adj)}
comp = collections.OrderedDict()
for c in ['knowledge-update', 'multi-session', 'single-session-assistant', 'single-session-preference', 'single-session-user', 'temporal-reasoning']:
    rs = [r for r in rows if r['competency'] == c]
    comp[c] = {'n': len(rs), 'pre': sum(pre(r) for r in rs), 'post': sum(bool(r['correct']) for r in rs)}
res['by_type'] = comp
# abstention questions: id convention _abs
absr = [r for r in rows if str(r['session_id']).endswith('_abs')]
res['abstention_questions'] = {'n': len(absr), 'correct_pre': sum(pre(r) for r in absr), 'correct_post': sum(bool(r['correct']) for r in absr)}
# Clopper-Pearson
from scipy.stats import beta
def cp(k, n, a=0.05):
    lo = 0.0 if k == 0 else beta.ppf(a / 2, k, n - k + 1); hi = 1.0 if k == n else beta.ppf(1 - a / 2, k + 1, n - k); return round(float(lo), 4), round(float(hi), 4)
res['clopper_pearson'] = {'128/180': cp(128, 180), '137/180': cp(137, 180), '0.711': 128 / 180, '0.761': 137 / 180}
json.dump(res, open(OUT + '/recompute_v12_grader.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
