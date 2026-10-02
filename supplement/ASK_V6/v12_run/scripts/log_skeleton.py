import re, sys, collections
p = sys.argv[1]
c = collections.Counter(); ex = {}
for i, l in enumerate(open(p, encoding='utf-8', errors='replace'), 1):
    l = l.rstrip('\n')
    sk = re.sub(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', '<UUID>', l)
    sk = re.sub(r'\b[0-9a-f]{8,}\b', '<HEX>', sk)
    sk = re.sub(r'\d+(\.\d+)?', '<N>', sk)
    sk = re.sub(r'(answer|sharegpt|ultrachat|evidence)_?[A-Za-z0-9_]*', '<SID>', sk)
    sk = sk[:110]
    c[sk] += 1; ex.setdefault(sk, i)
for sk, n in c.most_common(40):
    print(n, ex[sk], sk)
