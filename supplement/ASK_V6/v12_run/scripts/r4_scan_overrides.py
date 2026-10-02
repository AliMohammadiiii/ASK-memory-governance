#!/usr/bin/env python3
"""Find every file in the V12 run directory containing the baseline override field names (counts only)."""
import os, sys, csv, collections
RUN = sys.argv[1]
needles = [b'judge_overridden', b'judge_original_correct', b'judge_original_rationale', b'pre_manual_adjudication', b'correct_pre_adjudication', b'manual_adjudication_overrides']
rows = []
for d, dirs, files in os.walk(RUN):
    for f in files:
        p = os.path.join(d, f)
        if f == 'range_0_179.jsonl' or f == '_shared_extraction_cache.jsonl': continue   # slice (benchmark data) is never opened
        try: data = open(p, 'rb').read()
        except Exception: continue
        c = {n.decode(): data.count(n) for n in needles}
        if any(c.values()): rows.append((os.path.relpath(p, RUN), c))
agg = collections.defaultdict(list)
for rel, c in rows:
    top = rel.split('/')[0]
    agg[top].append((rel, {k: v for k, v in c.items() if v}))
for top, lst in agg.items():
    print('==', top, len(lst), 'files')
    for rel, c in lst[:14]: print('  ', rel, c)
