"""Claim check 3: R1 decision-rule replay of the merged V12 action log with the baseline-commit scorecard (default configuration).
Uses only the logged numeric features, the type and the stored action; candidate text is not read. Counts and deviations only."""
import sys, json, collections, importlib
sys.dont_write_bytecode = True
sys.path.insert(0, '/tmp/ask_base_src')
pol = importlib.import_module('ask.controller.policy'); feat = importlib.import_module('ask.controller.features')
V = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs_local/lme_final_controller_v12_qwen_180/controller/action_log.jsonl'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
rows = [json.loads(l) for l in open(V) if l.strip()]
mism = collections.Counter(); maxdev = collections.defaultdict(float); n = 0
for r in rows:
    fs = feat.FeatureSnapshot(c=r['feature_c'], e=r['feature_e'], f=r['feature_f'], r=r['feature_r'], rho=r['feature_rho'])
    d = pol.decide(fs, r['candidate_type'])
    n += 1
    if d.action.value != r['action']: mism['action'] += 1
    for k, a, b in (('s_rev', d.s_rev, r['s_rev']), ('s_abs', d.s_abs, r['s_abs']), ('theta_sup', d.theta_sup, r['theta_sup']), ('theta_abs', d.theta_abs, r['theta_abs'])):
        dev = abs(a - b); maxdev[k] = max(maxdev[k], dev)
        if dev > 0: mism[k + '_nonzero_dev'] += 1
    if d.rationale != r['rationale']: mism['rationale_text'] += 1
res = {'rows': n, 'mismatch_counts': dict(mism), 'max_abs_dev': dict(maxdev), 'distinct_action_values_in_log': dict(collections.Counter(r['action'] for r in rows))}
json.dump(res, open(OUT + '/recompute_r1_replay.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
