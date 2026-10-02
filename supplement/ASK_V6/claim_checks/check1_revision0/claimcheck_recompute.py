#!/usr/bin/env python3
"""Aggregate-only recomputation used by the claim check (no benchmark text is read into output).

Run with the environment 'ask-audit' (numpy, scipy). Read-only on all inputs.
Output: claimcheck_recomputed.json next to this script.
"""
import collections, csv, glob, hashlib, json, os, sys

import numpy as np
from scipy.stats import beta

AUD = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/'
REPO = '/Users/alimohammadi/Workspace/research/ASK-memory-governance'
BK = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs_local/'
V = BK + 'lme_final_controller_v12_qwen_180'
PP = BK + 'lme_final_controller_180_providerpool'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'claimcheck_recomputed.json')
res = {}


def jl(p):
    with open(p, encoding='utf8') as f:
        return [json.loads(l) for l in f if l.strip()]


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


# ---- MGP-6 v4.3 hidden aggregates (tracked analysis JSON) ----
d = json.load(open(REPO + '/artifacts/analysis/mgp6_v43_full_benchmark_analysis.json'))
h = d['hidden_v43']
conf = h['confusion']
errs = {g: sum(v for p, v in row.items() if p != g) for g, row in conf.items()}
res['hidden'] = {
    'accuracy': h['accuracy'], 'n_correct': sum(conf[g][g] for g in conf), 'n': h['n'],
    'wilson95': h['wilson95'], 'cluster_ci_acc': h['cluster_ci_acc'], 'cluster_ci_mf1': h['cluster_ci_mf1'],
    'macro_f1': h['macro_f1'], 'mcc': h['mcc'], 'kappa': h['kappa'], 'confusion_gold_rows': conf,
    'errors_by_gold': errs, 'total_errors': sum(errs.values()),
    'share_errors_gold_abstain': errs['ABSTAIN'] / sum(errs.values()),
    'non_abstain_predictions': sum(conf[g][p] for g in conf for p in conf[g] if p != 'ABSTAIN'),
    'non_abstain_correct': conf['KEEP']['KEEP'] + conf['SUPERSEDE']['SUPERSEDE'],
    'guard': h['guard']['transitions'], 'model_abstain_outputs': h['guard']['model_actions']['ABSTAIN'],
    'fallbacks': h['operational']['fallbacks'],
}
res['dev_table2'] = {k: [d['dev_systems'][k]['accuracy'], d['dev_systems'][k]['macro_f1']] for k in
                     ['live_model_controller', 'decision_zero_shot', 'b1', 'b2', 'b3', 'b4', 'ablation_no_abstain',
                      'ablation_no_typing', 'ablation_no_lineage', 'ablation_no_provenance']}

# ---- 2x2 decomposition from raw results (public dev ids and labels only) ----
dev = jl(REPO + '/benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl')
gold = {r['public_id']: r['gold_action'] for r in dev}
ids = sorted(gold)
rows = jl(AUD + 'phase13_routing_check/results.jsonl')
corr, pred = {}, {}
cells = ['A_zero_payload', 'D_zero_routed', 'E_live_payload', 'B_live_routed']
for c in cells:
    for rep in (0, 1):
        m = {r['public_id']: r['action'] for r in rows if r['cell'] == c and r['repeat'] == rep}
        assert set(m) == set(ids)
        pred[(c, rep)] = m
        corr[(c, rep)] = np.array([m[i] == gold[i] for i in ids], float)
acts = ['KEEP', 'SUPERSEDE', 'ABSTAIN']


def conf_rep(m):
    cm = collections.Counter((gold[i], m[i]) for i in ids)
    return [[cm[(g, p)] for p in acts] for g in acts]


res['twobytwo'] = {'accuracy': {c: [float(corr[(c, 0)].mean()), float(corr[(c, 1)].mean())] for c in cells},
                   'confusion_repeat0_rows_K_S_A': {c: conf_rep(pred[(c, 0)]) for c in cells},
                   'returned_models': dict(collections.Counter(r['returned_model'] for r in rows)),
                   'requested_models': dict(collections.Counter(r['requested_model'] for r in rows)),
                   'reasoning_tokens_present': sum(1 for r in rows if (r['usage'].get('completion_tokens_details') or {}).get('reasoning_tokens', 0) > 0)}


def pb(c1, c0, B=10000, seed=0):
    rng = np.random.default_rng(seed)
    dd = (corr[(c1, 0)] + corr[(c1, 1)]) / 2 - (corr[(c0, 0)] + corr[(c0, 1)]) / 2
    idx = rng.integers(0, len(ids), (B, len(ids)))
    bs = dd[idx].mean(1)
    return [float(dd.mean()), [float(x) for x in np.percentile(bs, [2.5, 97.5])]]


res['twobytwo']['contrasts'] = {'prompt_full': pb('E_live_payload', 'A_zero_payload'),
                                'prompt_routed': pb('B_live_routed', 'D_zero_routed'),
                                'routing_oneline': pb('D_zero_routed', 'A_zero_payload'),
                                'routing_live': pb('B_live_routed', 'E_live_payload'),
                                'total': pb('B_live_routed', 'A_zero_payload')}

# ---- LongMemEval V12 judgments ----
cj = jl(V + '/controller/judgments.jsonl')
orig = {}
for s in range(8):
    p = f'{V}/controller/_shard{s}/judgments.jsonl.pre_manual_adjudication.orig'
    if os.path.exists(p):
        for r in jl(p):
            orig[r['session_id']] = r
raw = {r['session_id']: (orig.get(r['session_id']) or r) for r in cj}
comp_final, comp_raw = collections.Counter(), collections.Counter()
for r in cj:
    comp_final[r['competency']] += bool(r['correct'])
    comp_raw[r['competency']] += bool(raw[r['session_id']]['correct'])
adj = [r for r in cj if r.get('adjudicated')]
nj = [r for r in cj if not r.get('judge_was_called')]
absq = [r for r in cj if r['session_id'].endswith('_abs')]
res['lme'] = {
    'n': len(cj), 'correct_final': sum(bool(r['correct']) for r in cj), 'correct_raw': sum(bool(r['correct']) for r in raw.values()),
    'by_competency_final': dict(comp_final), 'by_competency_raw': dict(comp_raw),
    'n_per_competency': dict(collections.Counter(r['competency'] for r in cj)),
    'adjudicated': len(adj), 'adjudicated_direction_pre_correct': dict(collections.Counter(bool(r['correct_pre_adjudication']) for r in adj)),
    'adjudicated_by_competency': dict(collections.Counter(r['competency'] for r in adj)),
    'adjudicated_with_judge_called': sum(bool(r.get('judge_was_called')) for r in adj),
    'not_model_judged': len(nj), 'not_model_judged_correct': sum(bool(r['correct']) for r in nj),
    'scoring_fallback': sum(bool(r.get('used_scoring_fallback')) for r in cj),
    'scoring_fallback_correct': sum(bool(r['correct']) for r in cj if r.get('used_scoring_fallback')),
    'abstention_questions': len(absq), 'abstention_correct_final': sum(bool(r['correct']) for r in absq),
    'raw_failures_by_competency': {k: 30 - v for k, v in comp_raw.items()},
    'clopper_pearson': {str(k): [float(beta.ppf(0.025, k, 180 - k + 1)), float(beta.ppf(0.975, k + 1, 180 - k))] for k in (128, 137)},
}
bl = {}
for b in ['b1', 'b2', 'b3', 'b4']:
    js = jl(f'{V}/{b}/judgments.jsonl')
    ov = [r for r in js if 'judge_overridden' in r]
    bl[b] = {'correct': sum(bool(r['correct']) for r in js), 'overrides': len(ov),
             'override_direction_orig_to_final': [[bool(r['judge_original_correct']), bool(r['correct'])] for r in ov],
             'identical_to_providerpool': sha(f'{V}/{b}/judgments.jsonl') == sha(f'{PP}/{b}/judgments.jsonl')}
res['baselines'] = bl

# ---- action log ----
rows_l = jl(V + '/controller/action_log.jsonl')
for r in rows_l:
    r['A'] = r['action'].upper()
W = dict(w1=1.0, w2=0.8, w3=0.7, w4=1.2, w5=0.5)
TS = {'stable_pref': 0.90, 'episodic_fact': 0.75, 'transient_pref': 0.55}
TA = {'stable_pref': 0.60, 'episodic_fact': 0.70, 'transient_pref': 0.80}
mism, maxdev = 0, 0.0
for r in rows_l:
    up = max(0.0, -r['feature_r'])
    srev = W['w1'] * r['feature_c'] + W['w2'] * r['feature_e'] - W['w3'] * r['feature_f'] + W['w4'] * up - W['w5'] * r['feature_rho']
    sabs = (1 - r['feature_c']) + r['feature_f'] + (1 - abs(r['feature_r']))
    t = r['candidate_type']
    act = 'ABSTAIN' if sabs > TA[t] else ('SUPERSEDE' if (srev > TS[t] and up > 0) else 'KEEP')
    mism += act != r['A']
    maxdev = max(maxdev, abs(srev - r['s_rev']), abs(sabs - r['s_abs']), abs(TS[t] - r['theta_sup']), abs(TA[t] - r['theta_abs']))


def H(s):
    return hashlib.sha256(s.encode()).hexdigest()


g = collections.defaultdict(list)
for r in rows_l:
    g[(r['session_id'], r['candidate_type'], H(r['candidate_text']))].append(r)
multi = {k: v for k, v in g.items() if len(v) > 1}
gg = collections.defaultdict(list)
for r in rows_l:
    gg[H(r['candidate_text'])].append(r)
pairs = collections.Counter((r['session_id'], r['candidate_id']) for r in rows_l)
kp = [r for r in rows_l if r['A'] == 'KEEP']
res['action_log'] = {
    'n': len(rows_l), 'sha256': sha(V + '/controller/action_log.jsonl'), 'actions': dict(collections.Counter(r['A'] for r in rows_l)),
    'types': dict(collections.Counter(r['candidate_type'] for r in rows_l)), 'sessions': len({r['session_id'] for r in rows_l}),
    'supersede_with_prior_and_result': sum(1 for r in rows_l if r['A'] == 'SUPERSEDE' and r['prior_memory_id'] is not None and r['resulting_memory_id'] is not None),
    'abstain_with_result': sum(1 for r in rows_l if r['A'] == 'ABSTAIN' and r['resulting_memory_id'] is not None),
    'keep_with_result': sum(1 for r in kp if r['resulting_memory_id'] is not None),
    'r1_mismatches_independent_reimplementation': mism, 'r1_max_abs_dev': maxdev,
    'rows_repeating_session_candidate_pair': sum(v - 1 for v in pairs.values() if v > 1),
    'repeated_text_groups_session_type_text': len(multi),
    'repeated_text_groups_diff_candidate_id': sum(1 for v in multi.values() if len({x['candidate_id'] for x in v}) > 1),
    'repeated_text_groups_diff_action': sum(1 for v in multi.values() if len({x['A'] for x in v}) > 1),
    'repeated_text_groups_global_text_only': sum(1 for v in gg.values() if len(v) > 1),
}
n_items = n_lines = none_valid = 0
for r in jl(V + '/controller/extraction_trace.jsonl'):
    n_lines += 1
    vo = r.get('validated_output')
    if vo is None:
        none_valid += 1
    else:
        n_items += len(vo['items'])
res['extraction'] = {'trace_rows': n_lines, 'validated_items': n_items, 'trace_rows_without_validated_output': none_valid}
ans = jl(V + '/controller/answers.jsonl')
res['answers'] = {'n': len(ans), 'seed_values': dict(collections.Counter(a.get('seed') for a in ans)),
                  'model_ids': dict(collections.Counter(a.get('model_id') for a in ans)),
                  'prior_top_k': dict(collections.Counter((a.get('extras') or {}).get('controller_prior_top_k') for a in ans))}
man = json.load(open(V + '/manifest.json'))
hom = json.load(open(V + '/homogeneity_report.json'))
res['manifest'] = {k: man.get(k) for k in ['status', 'exit_code', 'shards', 'freeze_version', 'judge_primary', 'judge_fallback', 'answer_provider_policy']}
res['manifest']['n_attempts'] = len(man['attempts'])
res['homogeneity'] = {'homogeneous': hom['homogeneous'], 'global_errors': hom['global_errors'],
                      'per_system_errors': {s['system']: s['errors'] for s in hom['systems']},
                      'seeds': hom['systems'][0]['seeds'], 'systems_checked': [s['system'] for s in hom['systems']]}
dm = json.load(open(REPO + '/artifacts/manifests/lme_v12_derived_manifest.json'))
res['derived_manifest_output_hashes_match'] = {k: sha(f'{V}/{k}') == v for k, v in dm['output_sha256'].items()}
res['derived_manifest_covers'] = sorted(dm['output_sha256'])
am = json.load(open(REPO + '/artifacts/analysis/lme_v12_adjacent_mcnemar.json'))
res['adjacent_mcnemar_baseline_hash_match'] = {b: sha(f'{V}/{b}/judgments.jsonl') == am['source_sha256'][b] for b in ['b1', 'b2', 'b3', 'b4']}
res['code_hashes_recovered_match'] = None
rec = AUD + 'phase15_v12_raw_evidence/recovered_evaluated_code.tar.gz'
res['recovered_code_tar_present'] = os.path.exists(rec)
print(json.dumps(res, indent=1)[:200])
json.dump(res, open(OUT, 'w'), indent=1, default=str)
print('written', OUT)
