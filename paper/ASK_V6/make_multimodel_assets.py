"""Builds the Phase 16 tables and figure for the paper from phase16_cluster_analysis.json (component-cluster intervals)."""
import json, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt, numpy as np
CAND = ['../phase16_qwen_routing_check/phase16_cluster_analysis.json', 'phase16_cluster_analysis.json', 'supplement/substitute_runs/analysis/phase16_cluster_analysis.json', '../ASK_supplement/substitute_runs/analysis/phase16_cluster_analysis.json']
C = json.load(open(next(p for p in CAND if __import__('os').path.exists(p))))['results']
NAMES = list(C.keys())
TOL, STR = 'json-fence-tolerant', 'baseline-strict'
def sgn(x, nd): return ('$-%.' + str(nd) + 'f$') % abs(x) if x < 0 and round(abs(x), nd) > 0 else ('$%.' + str(nd) + 'f$') % abs(x)
def con(c):
    d = c['diff']; lo, hi = c['ci95_cluster']
    return '$%+.3f$ (%s, %s)' % (d, sgn(lo, 2), sgn(hi, 2))
SHORT = {'Gemini 3.8 Flash (low)': 'Gemini low', 'Gemini 3.8 Flash (medium)': 'Gemini medium', 'Gemini 3.8 Flash (high, 1 repeat)': 'Gemini high (1 repeat)', 'GLM 5.3 Flash': 'GLM 5.3 Flash', 'gpt-oss-120b (medium)': 'gpt-oss-120b'}
short = lambda n: SHORT[n]
acc = ['\\begin{tabularx}{\\linewidth}{lYYYYY}', '\\toprule', 'Model & A & D & E & B & B+g \\\\', '\\midrule']
for n in NAMES:
    a = C[n][TOL]['accuracy_mean']
    acc.append('%s & %.3f & %.3f & %.3f & %.3f & %.3f \\\\' % (short(n), a['A_zero_payload'], a['D_zero_routed'], a['E_live_payload'], a['B_live_routed'], a['B_guarded']))
acc += ['\\bottomrule', '\\end{tabularx}']
open('tables/tab_models_acc.tex', 'w').write('\n'.join(acc) + '\n')
pr = ['\\begin{tabularx}{\\linewidth}{lYYY}', '\\toprule', 'Model & Prompt, payload (E$-$A) & Prompt, routed (B$-$D) & Both (B$-$A) \\\\', '\\midrule']
ro = ['\\begin{tabularx}{\\linewidth}{lYY}', '\\toprule', 'Model & Routing, one-line (D$-$A) & Routing, live (B$-$E) \\\\', '\\midrule']
for n in NAMES:
    k = C[n][TOL]['contrasts']
    pr.append('%s & %s & %s & %s \\\\' % (short(n), con(k['prompt_given_payload_E-A']), con(k['prompt_given_routed_B-D']), con(k['total_B-A'])))
    ro.append('%s & %s & %s \\\\' % (short(n), con(k['routing_given_oneline_D-A']), con(k['routing_given_live_B-E'])))
pr += ['\\bottomrule', '\\end{tabularx}']; ro += ['\\bottomrule', '\\end{tabularx}']
open('tables/tab_models_prompt.tex', 'w').write('\n'.join(pr) + '\n'); open('tables/tab_models_routing.tex', 'w').write('\n'.join(ro) + '\n')
# parser sensitivity (appendix)
ps = ['\\begin{tabularx}{\\linewidth}{llYYYYYr}', '\\toprule', 'Model & Rule & A & D & E & B & B+g & Rejected \\\\', '\\midrule']
for n in NAMES:
    for rule, lab in ((TOL, 'tolerant'), (STR, 'strict')):
        r = C[n][rule]; a = r['accuracy_mean']; inv = sum(sum(v) for v in r['invalid_by_repeat'].values()); tot = sum(len(r['repeats']) * 180 for _ in r['invalid_by_repeat'])
        ps.append('%s & %s & %.3f & %.3f & %.3f & %.3f & %.3f & %s \\\\' % (short(n) if lab == 'tolerant' else '', lab, a['A_zero_payload'], a['D_zero_routed'], a['E_live_payload'], a['B_live_routed'], a['B_guarded'], '%d of %d' % (inv, tot) if lab == 'strict' else '0'))
    ps.append('\\addlinespace')
ps = ps[:-1] + ['\\bottomrule', '\\end{tabularx}']
open('tables/tab_parser_sensitivity.tex', 'w').write('\n'.join(ps) + '\n')
# figure (tolerant rule; repeats as points)
plt.rcParams.update({'font.size': 8, 'axes.labelsize': 8, 'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5, 'axes.spines.top': False, 'axes.spines.right': False, 'pdf.fonttype': 42})
fig, axs = plt.subplots(1, 5, figsize=(7.4, 2.6), dpi=300, sharey=True)
col = {'zero': '#6b7a8f', 'live': '#c0504d'}
for ax, n in zip(axs, NAMES):
    r = C[n][TOL]; ab = r['accuracy_by_repeat']; am = r['accuracy_mean']
    for kind, cs in (('zero', ('A_zero_payload', 'D_zero_routed')), ('live', ('E_live_payload', 'B_live_routed'))):
        ax.plot([0, 1], [am[cs[0]], am[cs[1]]], '-', color=col[kind], lw=1.5, zorder=2)
        for xi, c in zip([0, 1], cs):
            v = ab[c]; ax.scatter([xi - 0.04, xi + 0.04][:len(v)], v, s=10, color=col[kind], zorder=3, edgecolor='white', linewidth=0.3)
    ax.set_xticks([0, 1]); ax.set_xticklabels(['Full\npayload', 'Routed\npair']); ax.set_xlim(-0.3, 1.3); ax.set_title(n.replace(' (', '\n('), fontsize=7, loc='left')
axs[0].set_ylim(0.3, 1.0); axs[0].set_yticks([0.4, 0.6, 0.8, 1.0]); axs[0].set_ylabel('Accuracy (n = 180)')
axs[0].text(1.05, 0.70, 'One-line\nprompt', color=col['zero'], fontsize=6, va='top', ha='left')
axs[0].text(1.05, 0.93, 'Live\nprompt', color=col['live'], fontsize=6, va='bottom', ha='left')
fig.tight_layout(w_pad=0.6); fig.savefig('figures/fig_models.pdf'); fig.savefig('figures/fig_models.png', dpi=200)
for f in ('tab_models_acc', 'tab_models_prompt', 'tab_models_routing', 'tab_parser_sensitivity'): print(open('tables/%s.tex' % f).read())
