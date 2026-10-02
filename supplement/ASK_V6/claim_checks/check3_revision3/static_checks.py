"""Claim check 3: static checks of the draft (citations, bib, labels/refs, banned words, dashes, em dash, figure files)."""
import re, os, json, glob, collections
D = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3/'
tex = {f: open(f).read() for f in [D + 'main.tex', D + 'author_info.tex'] + sorted(glob.glob(D + 'sections/*.tex')) + sorted(glob.glob(D + 'tables/*.tex'))}
alltex = '\n'.join(tex.values())
res = {}
cites = collections.Counter()
for m in re.finditer(r'\\cite[tp]?\*?(?:\[[^\]]*\])*\{([^}]*)\}', alltex):
    for k in m.group(1).split(','): cites[k.strip()] += 1
bib = open(D + 'references.bib').read()
keys = re.findall(r'@\w+\{([^,\s]+),', bib)
res['bib_entries'] = len(keys); res['bib_dup_keys'] = [k for k, c in collections.Counter(keys).items() if c > 1]
res['cited_keys'] = len(cites); res['cited_not_in_bib'] = sorted(set(cites) - set(keys)); res['bib_not_cited'] = sorted(set(keys) - set(cites))
core = open(D + 'references_core.bib').read(); res['references_core_keys'] = re.findall(r'@\w+\{([^,\s]+),', core)
labels = re.findall(r'\\label\{([^}]+)\}', alltex)
refs = re.findall(r'\\(?:ref|eqref|pageref)\{([^}]+)\}', alltex)
res['labels'] = len(labels); res['dup_labels'] = [k for k, c in collections.Counter(labels).items() if c > 1]
res['undefined_refs'] = sorted(set(refs) - set(labels)); res['unused_labels'] = sorted(set(labels) - set(refs))
# banned words (case-insensitive) in prose of sections + abstract
words = ['first', 'unique', 'novel', 'solves', 'safe', 'demonstrates', 'demonstrate', 'state of the art', 'state-of-the-art', 'unprecedented', 'production-ready', 'outperform', 'superior', 'prove', 'proves', 'causes', 'drives', 'explains', 'effect', 'mechanism', 'responsible', 'separates', 'because', 'therefore', 'new', 'best', 'significant', 'improve', 'validate', 'robust']
hits = collections.defaultdict(list)
for f, t in tex.items():
    for i, line in enumerate(t.splitlines(), 1):
        low = re.sub(r'\\cite[tp]?\{[^}]*\}', '', line).lower()
        for w in words:
            for m in re.finditer(r'\b' + re.escape(w) + r'\b', low):
                hits[w].append((os.path.relpath(f, D), i, low[max(0, m.start() - 50):m.end() + 40].strip()))
res['banned_word_hits'] = {w: len(v) for w, v in hits.items()}
json.dump({w: v for w, v in hits.items()}, open(OUT + 'static_word_hits.json', 'w'), indent=1)
# dashes
res['em_dash'] = sum(t.count('\u2014') for t in tex.values()); res['en_dash_unicode'] = sum(t.count('\u2013') for t in tex.values())
res['latex_triple_hyphen'] = sum(t.count('---') for t in tex.values()); res['latex_double_hyphen'] = [(os.path.relpath(f, D), i, l.strip()[:90]) for f, t in tex.items() for i, l in enumerate(t.splitlines(), 1) if '--' in l and '---' not in l and 'Clopper' not in l][:10]
# figures
inc = re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', alltex)
res['figures_included'] = inc; res['figure_files_exist'] = {i: os.path.exists(D + i) for i in inc}
res['inputs'] = re.findall(r'\\input\{([^}]+)\}', alltex)
res['input_exists'] = {i: os.path.exists(D + i + '.tex') for i in res['inputs']}
# env balance
for env in ['table', 'itemize', 'enumerate', 'description', 'tabular', 'tabularx', 'abstract', 'figure']:
    res.setdefault('env_balance', {})[env] = (len(re.findall(r'\\begin\{' + env + r'\}', alltex)), len(re.findall(r'\\end\{' + env + r'\}', alltex)))
res['uses_tabularx_pkg'] = 'tabularx' in tex[D + 'main.tex']; res['uses_enumitem_nosep'] = 'nosep' in alltex
res['footnote_or_unicode_nonascii'] = sorted({c for t in tex.values() for c in t if ord(c) > 127})
json.dump(res, open(OUT + 'static_checks.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ('labels',)}, indent=1)[:5000])
