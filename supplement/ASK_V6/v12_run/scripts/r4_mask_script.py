#!/usr/bin/env python3
"""Produce a masked rendering of a Python script: string literals that are not identifiers, file names or snake_case field names are replaced
by <str N chars>, so that benchmark-derived free text embedded in the script is not displayed. Comments are masked beyond 60 characters."""
import sys, tokenize, io, re
src = open(sys.argv[1], encoding='utf-8').read()
ok = re.compile(r'^(?:[a-z][a-z0-9_]*|[A-Za-z0-9_./-]+\.(?:jsonl|json|orig|md|py)|[0-9a-f]{8}|gpt4_[0-9a-f]{8}|[A-Za-z0-9_-]{1,3}|utf-8|__main__|manual|yes|no|true|false)$')
out = []
toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
res = []
for t in toks:
    s = t.string
    if t.type == tokenize.STRING:
        m = re.match(r'^([rbfuRBFU]*)(\'\'\'|"""|\'|")(.*)(\2)$', s, re.S)
        if m:
            body = m.group(3)
            if not ok.match(body): s = f'{m.group(1)}{m.group(2)}<str {len(body)} chars>{m.group(2)}'
        else: s = '<str>'
    elif t.type == tokenize.COMMENT and len(s) > 70:
        s = s[:60] + '<...>'
    res.append((t.type, s, t.start, t.end, t.line))
# reconstruct preserving line layout
lines = {}
for typ, s, (sr, sc), (er, ec), line in res:
    if typ in (tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER): continue
    if typ == tokenize.INDENT or typ == tokenize.DEDENT: continue
    lines.setdefault(sr, []).append((sc, s))
for n in sorted(lines):
    row = sorted(lines[n]); text = ''; col = 0
    for sc, s in row:
        text += ' ' * max(0, sc - col) + s; col = sc + len(s)
    out.append(f'{n:4d}| {text}')
open(sys.argv[2], 'w').write('\n'.join(out))
print(len(out), 'lines written to', sys.argv[2])
