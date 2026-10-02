#!/usr/bin/env python3
"""Print keys, value types and lengths (never values) of the first record of selected JSONL files in the V12 controller run."""
import json, sys, os
D = sys.argv[1]
def sch(o, depth=0, maxd=3):
    if isinstance(o, dict):
        return {k: (sch(v, depth+1, maxd) if depth < maxd else type(v).__name__) for k, v in o.items()}
    if isinstance(o, list):
        return ['list[%d]' % len(o)] + ([sch(o[0], depth+1, maxd)] if o and depth < maxd else [])
    if isinstance(o, str): return 'str(len=%d)' % len(o)
    return type(o).__name__
for rel in sys.argv[2:]:
    p = os.path.join(D, rel)
    with open(p, 'rb') as f:
        line = f.readline()
    n = 0
    with open(p, 'rb') as f:
        for _ in f: n += 1
    print('==', rel, 'lines=%d' % n)
    print(json.dumps(sch(json.loads(line)))[:1800])
