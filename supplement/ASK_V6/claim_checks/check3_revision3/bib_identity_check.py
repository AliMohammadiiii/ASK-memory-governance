"""Claim check 3: compare each bibliography entry (title, arXiv id) with the supplied identity files (dossier index, new candidates).
This is a file-consistency check only; it does not verify the documents themselves."""
import re, csv, json, difflib
D = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/'
OUT = D + 'paper_arxiv_draft/review_claimcheck3/'
bib = open(D + 'paper_arxiv_draft/references.bib', encoding='utf-8').read()
entries = re.findall(r'@(\w+)\{([^,\s]+),(.*?)\n\}', bib, flags=re.S)
def field(body, name):
    m = re.search(name + r'\s*=\s*[\{"](.*?)[\}"]\s*,?\s*\n', body, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', m.group(1)).strip('{} ') if m else ''
src = []
for r in csv.DictReader(open(D + 'ASK_supplement/related_work/COMPARATOR_DOSSIER_INDEX.csv', newline='', encoding='utf-8-sig')):
    src.append(('dossier', r['short_name'], r['canonical_title'], r['arxiv_id'], r['doi']))
for r in csv.DictReader(open(D + 'phase9_saturation/NEW_CANDIDATES.csv', newline='', encoding='utf-8-sig')):
    src.append(('new_candidates', r['short_name'], r['title'], r['arxiv_id'], r['doi']))
norm = lambda s: re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()
out = []
for typ, key, body in entries:
    title = field(body, 'title'); eprint = field(body, 'eprint') or field(body, 'arxiv') or field(body, 'url')
    m = re.search(r'(\d{4}\.\d{4,5})', eprint + ' ' + key.replace('_', '.') + ' ' + body)
    aid = ''
    km = re.match(r'arxiv_(\d{4})_(\d{4,5})', key)
    if km: aid = f'{km.group(1)}.{km.group(2)}'
    hit = [s for s in src if aid and aid in (s[3] or '')]
    status = 'NO_SOURCE_FILE_MATCH'; sim = None
    if hit:
        sim = max(difflib.SequenceMatcher(None, norm(title), norm(h[2])).ratio() for h in hit)
        status = 'ID_MATCH_TITLE_OK' if sim >= 0.8 else 'ID_MATCH_TITLE_DIFFERS'
    elif not aid:
        cand = max(src, key=lambda s: difflib.SequenceMatcher(None, norm(title), norm(s[2])).ratio())
        sim = difflib.SequenceMatcher(None, norm(title), norm(cand[2])).ratio()
        status = 'TITLE_MATCH_OK' if sim >= 0.8 else 'NO_SOURCE_FILE_MATCH'
    out.append({'key': key, 'bib_title': title[:90], 'arxiv_from_key': aid, 'status': status, 'title_similarity': None if sim is None else round(sim, 2), 'source': hit[0][0] + ':' + hit[0][1] if hit else ''})
json.dump(out, open(OUT + 'bib_identity_check.json', 'w'), indent=1)
import collections
print(collections.Counter(o['status'] for o in out))
for o in out:
    if o['status'] != 'ID_MATCH_TITLE_OK': print(o)
