import csv, collections, hashlib, json
exec(open('/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3/rows_part5.py').read())
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3/'
with open(OUT + 'CLAIM_CHECK3_REPORT.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['id', 'area', 'file', 'location', 'claim', 'verdict', 'evidence', 'fix'])
    for i, (area, file, loc, claim, verdict, evidence, fix) in enumerate(ROWS, 1):
        assert verdict in (S, W, C, U), verdict
        if verdict != S and not fix.strip(): fix = 'Keep as an author statement if confirmed, add the supporting record to the supplement, or soften to "to our knowledge".'
        assert '\u2014' not in (claim + evidence + fix) and '\u2013' not in (claim + evidence + fix)
        w.writerow(['CC3-%03d' % i, area, file, loc, claim, verdict, evidence, fix])
print(len(ROWS), collections.Counter(r[4] for r in ROWS))
print(collections.Counter(r[0] for r in ROWS))
print(hashlib.sha256(open(OUT + 'CLAIM_CHECK3_REPORT.csv', 'rb').read()).hexdigest())
