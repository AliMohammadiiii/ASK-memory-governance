#!/usr/bin/env python3
"""Claim check 2, Part A: independent recomputation of the Section 4 decomposition (Tables models-acc and models-con)
from raw per-call rows, plus Appendix E run metadata and several Section 4/5 statements.

Inputs (read only):
  * baseline snapshot of the repository at commit f6bf66e4766d769727edf6b42c76b9977b14978a, exported with `git archive`
    into /tmp/cc2_base (the repository itself is not touched);
  * raw per-call result rows (public development items only, no item text is stored in them):
      phase13_routing_check/results.jsonl              (Gemini 3.8 Flash low)
      phase16_qwen_routing_check/out_*/results.jsonl   (the other four configurations)
  * the V12 backup run directory (aggregates only; no answer/question text is read into any output).
Output: claimcheck2_recomputed.json (aggregates only; no item text, no gold text).
Nothing from multi_model_analysis.json is used for the numbers (it is read only for a final cross-comparison).
"""
import sys, os, json, glob, hashlib, re, collections, datetime
sys.dont_write_bytecode = True
import numpy as np

AUD = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927'
BASE = '/tmp/cc2_base'                      # git archive of f6bf66e4766d769727edf6b42c76b9977b14978a
OUT = AUD + '/paper_arxiv_draft/review_claimcheck2'
sys.path.insert(0, BASE + '/src')
from ask.eval.mgp6_v43 import (load_public_records, apply_live_controller_guard, build_system_prompt,
                               parse_action_response)

ACT = ['KEEP', 'SUPERSEDE', 'ABSTAIN']
DEV = BASE + '/benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl'
CFG = BASE + '/configs/experiments/mgp6_v43/'
EXPECT_DEV = 'd4dbf740d9fa5239829842e2ab6f5ce67b11d6d909628ff38f4a19fc0242cde5'
res = {'baseline_commit': 'f6bf66e4766d769727edf6b42c76b9977b14978a'}
dev_sha = hashlib.sha256(open(DEV, 'rb').read()).hexdigest()
res['dev_sha256'] = dev_sha; res['dev_sha256_matches_tracked'] = dev_sha == EXPECT_DEV
recs = load_public_records(DEV); assert len(recs) == 180
byid = {r.public_id: r for r in recs}; ids = sorted(byid); gold = {i: byid[i].gold_action for i in ids}
res['dev_gold_distribution'] = dict(collections.Counter(gold.values()))
zero = open(CFG + 'decision_system_prompt.txt', encoding='utf-8').read(); live = open(CFG + 'live_model_controller_prompt.txt', encoding='utf-8').read()
CELLDEF = {'A_zero_payload': ('decision_zero_shot', zero), 'B_live_routed': ('live_model_controller', live),
           'D_zero_routed': ('live_model_controller', zero), 'E_live_payload': ('decision_zero_shot', live)}
rebuilt = {}
for c, (sysname, ptxt) in CELLDEF.items():
    for i in ids:
        p = build_system_prompt(byid[i], sysname, ptxt)
        rebuilt[(i, c)] = (hashlib.sha256(p.encode()).hexdigest(), len(p))

CONFIGS = [  # label, results file, how the run was parameterized (summary.json where present)
    ('Gemini 3.8 Flash (low)', AUD + '/phase13_routing_check/results.jsonl', None),
    ('Gemini 3.8 Flash (medium)', AUD + '/phase16_qwen_routing_check/out_ag_gemini-3.8-flash-medium/results.jsonl', AUD + '/phase16_qwen_routing_check/out_ag_gemini-3.8-flash-medium/summary.json'),
    ('Gemini 3.8 Flash (high, 1 repeat)', AUD + '/phase16_qwen_routing_check/out_ag_gemini-3.8-flash-high/results.jsonl', AUD + '/phase16_qwen_routing_check/out_ag_gemini-3.8-flash-high/summary.json'),
    ('GLM 5.3 Flash', AUD + '/phase16_qwen_routing_check/out_ocg_glm-5.3-flash/results.jsonl', AUD + '/phase16_qwen_routing_check/out_ocg_glm-5.3-flash/summary.json'),
    ('gpt-oss-120b (medium)', AUD + '/phase16_qwen_routing_check/out_ag_gpt-oss-120b-medium/results.jsonl', AUD + '/phase16_qwen_routing_check/out_ag_gpt-oss-120b-medium/summary.json'),
]
CELLS = ['A_zero_payload', 'D_zero_routed', 'E_live_payload', 'B_live_routed']

# independent bootstrap: 10,000 item resamples, seed 0, items resampled and repeats averaged within item
B = 10000
rng = np.random.default_rng(0); IDX = rng.integers(0, 180, size=(B, 180))
rs = np.random.RandomState(0); IDX_ALT = rs.randint(0, 180, size=(B, 180))      # different generator, sensitivity only
def boot(delta, idx=IDX):
    bs = delta[idx].mean(1)
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
def macro_f1(y, p):
    f = []
    for c in ACT:
        tp = sum(g == c and q == c for g, q in zip(y, p)); fp = sum(g != c and q == c for g, q in zip(y, p)); fn = sum(g == c and q != c for g, q in zip(y, p))
        f.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return sum(f) / 3

res['configs'] = {}
y = [gold[i] for i in ids]
for label, rf, sf in CONFIGS:
    rows_all = [json.loads(l) for l in open(rf, encoding='utf-8') if l.strip()]
    lat = {}
    for j in rows_all: lat[(j['public_id'], j['cell'], j['repeat'])] = j              # last row wins
    reps = sorted({k[2] for k in lat})
    m = {'file': rf.replace(AUD + '/', ''), 'n_rows_in_file': len(rows_all), 'n_unique_keys': len(lat), 'repeats': reps,
         'models_requested': sorted({j.get('requested_model') for j in rows_all}), 'returned_model': sorted({str(j.get('returned_model')) for j in rows_all}),
         'n_action_FAILED_in_file': sum(j['action'] == 'FAILED' for j in rows_all),
         'n_action_FAILED_after_last_wins': sum(j['action'] == 'FAILED' for j in lat.values())}
    # prompt identity: every row's prompt hash against the baseline-commit builders
    mism = 0; checked = 0
    for (i, c, rep), j in lat.items():
        checked += 1
        if j['prompt_sha256'] != rebuilt[(i, c)][0]: mism += 1
    m['prompt_hash_checked'] = checked; m['prompt_hash_mismatch_vs_baseline_builders'] = mism
    corr = {c: {} for c in CELLS + ['B_guarded']}; accs = {c: {} for c in CELLS + ['B_guarded']}; mf1 = {c: {} for c in CELLS + ['B_guarded']}
    preds = {c: {} for c in CELLS + ['B_guarded']}; nonvalid = collections.Counter()
    for rep in reps:
        for c in CELLS + ['B_guarded']:
            src = 'B_live_routed' if c == 'B_guarded' else c
            pr = []
            for i in ids:
                a = lat[(i, src, rep)]['action']
                if a not in ACT: nonvalid[(c, rep)] += 1
                if c == 'B_guarded' and a in ACT: a = apply_live_controller_guard(byid[i], a)[0]
                pr.append(a)
            preds[c][rep] = pr
            corr[c][rep] = np.array([float(g == p) for g, p in zip(y, pr)])
            accs[c][rep] = float(corr[c][rep].mean()); mf1[c][rep] = macro_f1(y, pr)
    m['nonvalid_predictions'] = {f'{c}|r{r}': v for (c, r), v in nonvalid.items()}
    m['acc_by_repeat'] = {c: {str(r): accs[c][r] for r in reps} for c in accs}
    m['macro_f1_by_repeat'] = {c: {str(r): mf1[c][r] for r in reps} for c in accs}
    m['acc_mean'] = {c: float(np.mean([accs[c][r] for r in reps])) for c in accs}
    m['pred_distribution_by_repeat'] = {f'{c}|r{r}': {a: preds[c][r].count(a) for a in ACT} for c in accs for r in reps}
    item_mean = {c: np.mean([corr[c][r] for r in reps], axis=0) for c in accs}
    def con(a, b):
        d = item_mean[a] - item_mean[b]
        return {'diff': float(d.mean()), 'ci95': boot(d), 'ci95_alt_generator': boot(d, IDX_ALT), 'n_items_better': int((d > 0).sum()), 'n_items_worse': int((d < 0).sum())}
    m['contrasts'] = {'prompt_payload': con('E_live_payload', 'A_zero_payload'), 'prompt_routed': con('B_live_routed', 'D_zero_routed'),
                      'routing_oneline': con('D_zero_routed', 'A_zero_payload'), 'routing_live': con('B_live_routed', 'E_live_payload'),
                      'B_minus_A': con('B_live_routed', 'A_zero_payload')}
    inter = (item_mean['B_live_routed'] - item_mean['D_zero_routed']) - (item_mean['E_live_payload'] - item_mean['A_zero_payload'])
    m['interaction_(B-D)-(E-A)'] = {'diff': float(inter.mean()), 'ci95': boot(inter)}
    # timestamps (run window) from the utc field of the rows actually used
    ts = sorted(datetime.datetime.fromisoformat(j['utc'].replace('Z', '+00:00')) for j in lat.values() if j.get('utc'))
    m['utc_first'] = ts[0].isoformat(); m['utc_last'] = ts[-1].isoformat()
    m['utc_first_to_last_minutes'] = round((ts[-1] - ts[0]).total_seconds() / 60, 1)
    # token limits, seeds, finish reasons
    m['max_tokens_in_rows'] = dict(collections.Counter(j.get('max_tokens') for j in lat.values()))
    m['finish_reason_in_rows'] = dict(collections.Counter(j.get('finish_reason') for j in lat.values()))
    m['attempts_dist'] = dict(collections.Counter(j.get('attempts') for j in lat.values()))
    if sf:
        s = json.load(open(sf)); m['summary_json'] = {k: s.get(k) for k in ('max_tokens', 'sent_seed', 'reasoning_effort_arg', 'model', 'dev_sha256', 'n_rows')}
    # parser sensitivity: rows whose reply is fully stored (<120 chars) re-parsed with the baseline-commit parser
    chg = collections.Counter(); tot = 0
    for j in lat.values():
        raw = j.get('raw')
        if raw is None or len(raw) >= 120: continue
        tot += 1
        try: pa = parse_action_response(raw)
        except Exception: pa = 'INVALID'
        if pa != j['action']: chg[(j['action'], pa)] += 1
    m['parser_sensitivity'] = {'rows_fully_stored': tot, 'rows_whose_stored_action_differs_from_baseline_parser': sum(chg.values()), 'transitions': {f'{a}->{b}': n for (a, b), n in chg.items()}}
    # prompt tokens vs prompt length: intercept of a linear fit estimates a constant overhead in tokens
    fit = {}
    for c in CELLS:
        xs = []; ys = []
        for (i, cc, rep), j in lat.items():
            if cc == c and j.get('usage') and j['usage'].get('prompt_tokens'):
                xs.append(rebuilt[(i, c)][1]); ys.append(j['usage']['prompt_tokens'])
        if len(xs) > 10:
            b1, b0 = np.polyfit(xs, ys, 1); fit[c] = {'n': len(xs), 'slope_tokens_per_char': float(b1), 'intercept_tokens': float(b0), 'mean_prompt_tokens': float(np.mean(ys)), 'mean_chars': float(np.mean(xs))}
    m['prompt_token_fit'] = fit
    rt = [j['usage']['completion_tokens_details']['reasoning_tokens'] for j in lat.values() if j.get('usage') and (j['usage'].get('completion_tokens_details') or {}).get('reasoning_tokens') is not None]
    m['reasoning_tokens_reported_rows'] = len(rt); m['reasoning_tokens_mean'] = float(np.mean(rt)) if rt else None
    m['completion_tokens_includes_reasoning_heuristic'] = None
    res['configs'][label] = m

# Extra A1: sensitivity of the accuracies to the reply parser. The stored `action` was produced at run time by the parser of the
# run script (phase13: first-brace-to-last-brace JSON extraction; phase16: the parser of the working tree at that moment).
# Here every fully stored reply is re-parsed with the parser of the baseline commit; a reply that it rejects is counted as incorrect.
for label, rf, sf in CONFIGS:
    lat = {}
    for l in open(rf, encoding='utf-8'):
        if l.strip(): j = json.loads(l); lat[(j['public_id'], j['cell'], j['repeat'])] = j
    reps = sorted({k[2] for k in lat}); sens = {}
    for c in CELLS:
        per = []
        for rep in reps:
            inval = 0; ok = 0
            for i in ids:
                j = lat[(i, c, rep)]
                try: pa = parse_action_response(j['raw'])
                except Exception: pa = 'INVALID'
                inval += pa == 'INVALID'; ok += pa == gold[i]
            per.append({'n_invalid_under_baseline_parser': inval, 'accuracy_invalid_as_wrong': ok / 180})
        sens[c] = per
    res['configs'][label]['baseline_parser_sensitivity'] = sens
# Extra A1b: the same re-parse with the parser of the current (uncommitted) working tree of the repository, loaded read-only from its file.
import importlib.util
_wt_path = '/Users/alimohammadi/Workspace/research/ASK-memory-governance/src/ask/eval/mgp6_v43.py'
_spec = importlib.util.spec_from_file_location('wt_mgp6_v43', _wt_path); _wt = importlib.util.module_from_spec(_spec); sys.modules['wt_mgp6_v43'] = _wt; _spec.loader.exec_module(_wt)
res['working_tree_parser_file_mtime_local'] = datetime.datetime.fromtimestamp(os.path.getmtime(_wt_path)).isoformat()
res['working_tree_parser_file_mtime_utc'] = datetime.datetime.fromtimestamp(os.path.getmtime(_wt_path), datetime.timezone.utc).isoformat()
for label, rf, sf in CONFIGS:
    n = 0; diff = 0
    for l in open(rf, encoding='utf-8'):
        if not l.strip(): continue
        j = json.loads(l)
        if j.get('raw') is None or len(j['raw']) >= 120 or j['action'] == 'FAILED': continue
        n += 1
        try: pa = _wt.parse_action_response(j['raw'])
        except Exception: pa = 'INVALID'
        diff += pa != j['action']
    res['configs'][label]['working_tree_parser_check'] = {'rows': n, 'stored_action_differs_from_working_tree_parser': diff}
# Extra A2: constant prompt-token overhead. tokens(E)-tokens(A) differ only by the live-vs-zero prompt text, which fixes tokens per character
# for prose of this kind; the residual of tokens(A) after removing chars(A)*ratio estimates what the gateway or tokenizer adds.
for label, rf, sf in CONFIGS:
    lat = {}
    for l in open(rf, encoding='utf-8'):
        if l.strip(): j = json.loads(l); lat[(j['public_id'], j['cell'], j['repeat'])] = j
    tok = {c: np.mean([j['usage']['prompt_tokens'] for (i, cc, rep), j in lat.items() if cc == c and j.get('usage')]) for c in CELLS}
    chars = {c: np.mean([rebuilt[(i, c)][1] for i in ids]) for c in CELLS}
    r1 = (tok['E_live_payload'] - tok['A_zero_payload']) / (chars['E_live_payload'] - chars['A_zero_payload'])
    r2 = (tok['B_live_routed'] - tok['D_zero_routed']) / (chars['B_live_routed'] - chars['D_zero_routed'])
    res['configs'][label]['prompt_overhead_estimate'] = {'tokens_per_char_from_prompt_difference_payload': float(r1), 'tokens_per_char_from_prompt_difference_routed': float(r2),
        'overhead_tokens_A_cell': float(tok['A_zero_payload'] - r1 * chars['A_zero_payload']), 'overhead_tokens_D_cell': float(tok['D_zero_routed'] - r2 * chars['D_zero_routed']),
        'mean_prompt_tokens': {c: float(v) for c, v in tok.items()}, 'mean_prompt_chars': {c: float(v) for c, v in chars.items()}}

# statements of Section 4
S = {}
bm = {k: v['contrasts']['B_minus_A']['diff'] for k, v in res['configs'].items()}
S['B_minus_A_by_config'] = bm; S['B_minus_A_min'] = min(bm.values()); S['B_minus_A_max'] = max(bm.values())
gp = res['configs']['gpt-oss-120b (medium)']['pred_distribution_by_repeat']
S['gpt_oss_A_repeat0_distribution'] = gp['A_zero_payload|r0']
gh = res['configs']['Gemini 3.8 Flash (high, 1 repeat)']['pred_distribution_by_repeat']
S['gemini_high_abstain_E_payload_live'] = gh['E_live_payload|r0']['ABSTAIN']; S['gemini_high_abstain_B_routed_live'] = gh['B_live_routed|r0']['ABSTAIN']
S['gold_ABSTAIN_dev'] = res['dev_gold_distribution'].get('ABSTAIN')
S['A_accuracy_min_max'] = [min(v['acc_mean']['A_zero_payload'] for v in res['configs'].values()), max(v['acc_mean']['A_zero_payload'] for v in res['configs'].values())]
S['highest_cell_any_config'] = max(((v['acc_mean'][c], k, c) for k, v in res['configs'].items() for c in v['acc_mean']), key=lambda t: t[0])
res['section4_statements'] = S

# compare with the numbers printed in the draft tables (parsed from the .tex files)
def parse_tex_rows(path):
    rows = []
    for line in open(path):
        if '&' in line and '\\\\' in line and not line.strip().startswith('\\toprule'):
            cells = [c.strip().rstrip('\\').strip() for c in line.strip().rstrip('\\\\').split('&')]
            rows.append(cells)
    return rows
DR = AUD + '/paper_arxiv_draft/'
acc_rows = [r for r in parse_tex_rows(DR + 'tables/tab_models_acc.tex') if r[0] != 'Model']
con_rows = [r for r in parse_tex_rows(DR + 'tables/tab_models_contrasts.tex') if r[0] != 'Model']
def num(s):
    return [float(x) for x in re.findall(r'-?\d+\.\d+', s.replace('$', '').replace('\\', ''))]
cmp = {'acc': [], 'con': []}
for r in acc_rows:
    lab = r[0]; v = res['configs'][lab]['acc_mean']
    paper = [float(x) for x in r[1:]]
    mine = [v['A_zero_payload'], v['D_zero_routed'], v['E_live_payload'], v['B_live_routed'], v['B_guarded']]
    cmp['acc'].append({'config': lab, 'paper': paper, 'recomputed_3dp': [round(x, 3) for x in mine], 'recomputed_exact': mine,
                       'max_abs_diff_vs_3dp': max(abs(p - round(x, 3)) for p, x in zip(paper, mine))})
keymap = ['prompt_payload', 'prompt_routed', 'routing_oneline', 'routing_live']
for r in con_rows:
    lab = r[0]
    for k, cell in zip(keymap, r[1:]):
        n = num(cell); c = res['configs'][lab]['contrasts'][k]
        cmp['con'].append({'config': lab, 'contrast': k, 'paper_diff': n[0], 'paper_ci': n[1:3], 'recomputed_diff': c['diff'], 'recomputed_ci': c['ci95'], 'recomputed_ci_alt_generator': c['ci95_alt_generator'],
                           'diff_mismatch_3dp': abs(n[0] - round(c['diff'], 3)) > 1e-9,
                           'ci_mismatch_2dp': [abs(n[1] - round(c['ci95'][0], 2)) > 1e-9, abs(n[2] - round(c['ci95'][1], 2)) > 1e-9],
                           'ci_mismatch_2dp_alt_generator': [abs(n[1] - round(c['ci95_alt_generator'][0], 2)) > 1e-9, abs(n[2] - round(c['ci95_alt_generator'][1], 2)) > 1e-9]})
res['table_comparison'] = cmp

# ------------------------------------------------------------------------------------------------------------------
# PART B numerics (aggregates only; the V12 judgments and the action log are read for counts, never printed)
# ------------------------------------------------------------------------------------------------------------------
from scipy.stats import beta as _beta
def cp(k, n):
    return [float(_beta.ppf(0.025, k, n - k + 1)), float(_beta.ppf(0.975, k + 1, n - k))]
def wilson(k, n, z=1.959963984540054):
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5
    return [(c - h) / d, (c + h) / d]
PB = {}
# hidden-split aggregates from the tracked analysis (no private file is opened)
tracked = json.load(open(BASE + '/artifacts/analysis/mgp6_v43_full_benchmark_analysis.json'))
hv = tracked['hidden_v43']; conf = hv['confusion']      # conf[gold][pred]
tot = sum(sum(r.values()) for r in conf.values()); corr_h = sum(conf[a][a] for a in conf)
pred_tot = {p: sum(conf[g][p] for g in conf) for p in ACT}
PB['hidden'] = {'n': tot, 'correct': corr_h, 'accuracy': corr_h / tot, 'wilson95': wilson(corr_h, tot), 'macro_f1_tracked': hv['macro_f1'], 'errors': tot - corr_h,
                'gold_ABSTAIN_errors': conf['ABSTAIN']['KEEP'] + conf['ABSTAIN']['SUPERSEDE'], 'false_commit_wilson95': wilson(conf['ABSTAIN']['KEEP'] + conf['ABSTAIN']['SUPERSEDE'], 180),
                'gold_SUPERSEDE_not_superseded': conf['SUPERSEDE']['KEEP'] + conf['SUPERSEDE']['ABSTAIN'], 'gold_KEEP_overwritten': conf['KEEP']['SUPERSEDE'],
                'non_abstain_predictions': tot - pred_tot['ABSTAIN'], 'correct_among_non_abstain': conf['KEEP']['KEEP'] + conf['SUPERSEDE']['SUPERSEDE'],
                'conditional_accuracy_after_abstention': (conf['KEEP']['KEEP'] + conf['SUPERSEDE']['SUPERSEDE']) / (tot - pred_tot['ABSTAIN']),
                'guard_tracked': hv['guard'], 'fallbacks_tracked': hv['operational'].get('fallbacks')}
# development table values from the tracked analysis
PB['dev_table_source'] = {k: [tracked['dev_systems'][k]['accuracy'], tracked['dev_systems'][k]['macro_f1']] for k in
                          ['live_model_controller', 'decision_zero_shot', 'b1', 'b2', 'b3', 'b4', 'ablation_no_abstain', 'ablation_no_typing', 'ablation_no_lineage', 'ablation_no_provenance']}
fr = json.load(open(BASE + '/configs/experiments/mgp6_v43/FROZEN_CONFIG_INDEX.json'))
PB['frozen_dev_run_metrics'] = fr['development_selection']['public_dev_metrics']
# pool structure and mean indexed position on the public components
def _info(r):
    snippets = {}
    for turn in r.dialogue:
        for ordinal, snippet in M_._EVIDENCE_MESSAGE_RE.findall(turn['text']):
            snippets[M_._ORDINAL_MESSAGE_POSITIONS[ordinal.casefold()]] = ' '.join(snippet.split())
    pos = [e['message_position'] for e in M_.linked_evidence_view(r)['indexed_evidence']]
    return snippets, pos, len(r.dialogue)
import ask.eval.mgp6_v43 as M_
tr_recs = M_.load_public_records(BASE + '/benchmarks/mgp6/mgp6_v4_3/public/train.jsonl')
pool = {}
for name, rr in [('train', tr_recs), ('dev', recs), ('train+dev', tr_recs + recs)]:
    rows = []
    for r in rr:
        sn, pos, L = _info(r); rows.append((json.dumps(r.memory_before, sort_keys=True), L, r.gold_action, sn, pos))
    tri = collections.defaultdict(list); comp = collections.defaultdict(list)
    for x in rows: tri[(x[0], x[1])].append(x); comp[x[0]].append(x)
    pk = lambda x: tuple(sorted(x[3].values()))
    same = sum(1 for v in tri.values() if len({pk(x) for x in v}) == 1)
    part = 0
    for v in tri.values():
        pairs = [frozenset(x[3][p] for p in x[4]) for x in v]
        if len(v) == 3 and len(set().union(*pairs)) == 6 and sum(len(p) for p in pairs) == 6: part += 1
    byact = collections.defaultdict(list)
    for x in rows: byact[x[2]].extend(x[4])
    pool[name] = {'items': len(rows), 'components': len(comp), 'component_length_triples': len(tri), 'triples_identical_pool': same, 'triples_partition': part,
                  'components_one_pool_across_lengths': sum(1 for v in comp.values() if len({pk(x) for x in v}) == 1),
                  'triples_numbering_differs': sum(1 for v in tri.values() if len({tuple(sorted((s, p) for p, s in x[3].items())) for x in v}) > 1),
                  'mean_indexed_position_by_action': {a: sum(v) / len(v) for a, v in byact.items()}, 'mean_indexed_position_all': sum(p for x in rows for p in x[4]) / (2 * len(rows)),
                  'position_sum_by_action': {a: sum(v) for a, v in byact.items()}}
PB['pool_public'] = pool
# V12 run directory (backup, read only): counts from judgments and the action log
V12 = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs_local/lme_final_controller_v12_qwen_180/controller'
def _load(pattern):
    d = {}
    for f in sorted(glob.glob(pattern)):
        for l in open(f):
            if l.strip(): j = json.loads(l); d[j['session_id']] = j
    return d
post = _load(V12 + '/_shard*/judgments.jsonl'); pre0 = _load(V12 + '/_shard*/judgments.jsonl.pre_manual_adjudication.orig'); pre = dict(post); pre.update(pre0)
def _path(r):
    return 'guard' if r.get('judge_was_called') is False else ('substring_fallback' if r.get('used_scoring_fallback') else 'model_judge')
def _comp(rows):
    c = collections.Counter((_path(r), bool(r['correct'])) for r in rows.values())
    return {f'{p}|{"correct" if ok else "incorrect"}': n for (p, ok), n in sorted(c.items())}
chg = [k for k in pre if bool(pre[k]['correct']) != bool(post[k]['correct'])]
types = sorted({r['competency'] for r in post.values()})
PB['v12_grader'] = {'n': len(post), 'n_pre_orig_files_rows': len(pre0), 'correct_pre': sum(bool(r['correct']) for r in pre.values()), 'correct_post': sum(bool(r['correct']) for r in post.values()),
                    'composition_pre_adjudication': _comp(pre), 'composition_post_adjudication': _comp(post),
                    'never_sent_to_judge': sum(1 for r in post.values() if r.get('judge_was_called') is False), 'judge_called': sum(1 for r in post.values() if r.get('judge_was_called') is True),
                    'changed': len(chg), 'changed_by_path': dict(collections.Counter(_path(pre[k]) for k in chg)), 'changed_by_type': dict(collections.Counter(pre[k]['competency'] for k in chg)),
                    'changed_direction_false_to_true': sum(1 for k in chg if (not pre[k]['correct']) and post[k]['correct']),
                    'by_type_pre_post': {t: [sum(bool(pre[k]['correct']) for k in post if post[k]['competency'] == t), sum(bool(post[k]['correct']) for k in post if post[k]['competency'] == t)] for t in types},
                    'abstention_questions': sum(1 for k in post if k.endswith('_abs')), 'abstention_correct_pre': sum(bool(pre[k]['correct']) for k in post if k.endswith('_abs')),
                    'abstention_correct_post': sum(bool(post[k]['correct']) for k in post if k.endswith('_abs')),
                    'clopper_pearson_128_180': cp(128, 180), 'clopper_pearson_137_180': cp(137, 180)}
# action log: counts and an independent R1 replay with the baseline-commit scorecard code
from ask.controller.policy import decide
from ask.controller.features import FeatureSnapshot
rows_al = [json.loads(l) for l in open(V12 + '/action_log.jsonl') if l.strip()]
al_sha = hashlib.sha256(open(V12 + '/action_log.jsonl', 'rb').read()).hexdigest()
mm = 0; maxdev = 0.0
for j in rows_al:
    d = decide(FeatureSnapshot(c=j['feature_c'], e=j['feature_e'], f=j['feature_f'], r=j['feature_r'], rho=j['feature_rho']), j['candidate_type'])
    if d.action.value != j['action']: mm += 1
    maxdev = max(maxdev, abs(d.s_rev - j['s_rev']), abs(d.s_abs - j['s_abs']), abs(d.theta_sup - j['theta_sup']), abs(d.theta_abs - j['theta_abs']))
acts = collections.Counter(j['action'] for j in rows_al)
pairs = collections.Counter((j['session_id'], j['candidate_id']) for j in rows_al)
texts = collections.defaultdict(set)
for j in rows_al: texts[j['candidate_text']].add(j['id'])
PB['v12_action_log'] = {'rows': len(rows_al), 'sha256': al_sha, 'sessions': len({j['session_id'] for j in rows_al}), 'actions': dict(acts), 'types': dict(collections.Counter(j['candidate_type'] for j in rows_al)),
                        'supersede_with_prior_and_resulting': sum(1 for j in rows_al if j['action'] == 'Supersede' and j['prior_memory_id'] is not None and j['resulting_memory_id'] is not None),
                        'abstain_with_resulting': sum(1 for j in rows_al if j['action'] == 'Abstain' and j['resulting_memory_id'] is not None),
                        'keep_with_resulting': sum(1 for j in rows_al if j['action'] == 'Keep' and j['resulting_memory_id'] is not None),
                        'duplicate_session_candidate_pairs': sum(1 for v in pairs.values() if v > 1) , 'extra_rows_in_duplicate_pairs': sum(v - 1 for v in pairs.values() if v > 1),
                        'R1_replay_action_mismatches': mm, 'R1_replay_max_abs_deviation': maxdev}
PB['v12_extraction'] = {'trace_rows': sum(1 for l in open(V12 + '/extraction_trace.jsonl') if l.strip()),
                        'validated_items_in_trace': sum(len(((json.loads(l)['validated_output'] or {}).get('items')) or []) for l in open(V12 + '/extraction_trace.jsonl') if l.strip())}
res['partB_numerics'] = PB
# cross-comparison with the author's file (not used for any number above)
try:
    mm = json.load(open(DR + 'supplement/multi_model_analysis.json'))
    res['author_json_keys'] = list(mm.keys())
except Exception as e:
    res['author_json_keys'] = str(e)
json.dump(res, open(OUT + '/claimcheck2_recomputed.json', 'w'), indent=1, default=str)
print('wrote', OUT + '/claimcheck2_recomputed.json')
