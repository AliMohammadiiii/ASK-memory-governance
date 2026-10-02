import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
# per-type correct answers out of 30, V12 controller-only run (aggregates from V12_RAW_ANALYSIS.json)
types = ['Knowledge update', 'Multi-session', 'Single-session assistant', 'Single-session preference', 'Single-session user', 'Temporal reasoning']
raw = [29, 19, 29, 9, 24, 18]
adj = [29, 19, 29, 16, 25, 19]
assert sum(raw) == 128 and sum(adj) == 137
plt.rcParams.update({'font.size': 8, 'axes.labelsize': 8, 'xtick.labelsize': 7, 'ytick.labelsize': 7, 'axes.spines.top': False, 'axes.spines.right': False, 'pdf.fonttype': 42})
fig, ax = plt.subplots(figsize=(4.8, 2.7), dpi=300)
ys = list(range(len(types)))[::-1]
for y, a, b in zip(ys, raw, adj):
    ax.plot([a, b], [y, y], '-', color='#9aa5b5', lw=1.5, zorder=1)
ax.scatter(raw, ys, s=22, color='#6b7a8f', zorder=2, label='Grader output')
ax.scatter(adj, ys, s=22, color='#c0504d', zorder=3, label='After nine adjudications')
ax.set_yticks(ys); ax.set_yticklabels(types); ax.set_xlim(5, 32); ax.set_xlabel('Correct answers out of 30')
ax.legend(frameon=False, loc='lower left', fontsize=7, handletextpad=0.3, borderaxespad=0.2)
fig.tight_layout(); fig.savefig('figures/fig_lme.pdf'); fig.savefig('figures/fig_lme.png', dpi=200)
