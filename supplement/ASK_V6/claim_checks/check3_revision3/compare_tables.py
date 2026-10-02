import json, re, sys
O='/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
D='/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft'
j=json.load(open(O+'/recompute_models.json'))['results']
def nums(s): 
    s=s.replace('$','').replace('\\,','')
    return [float(x.replace('−','-')) for x in re.findall(r'[-+]?\d+\.\d+', s)]
disc=[]; n=0
def chk(label, paper, mine, tol=0.0005):
    global n; n+=1
    ok = abs(round(mine,3)-paper)<=tol+1e-9
    if not ok: disc.append((label,paper,round(mine,4)))
# acc table
names=['Gemini low','Gemini medium','Gemini high (1 repeat)','GLM 5.3 Flash','gpt-oss-120b']
cells=['A_zero_payload','D_zero_routed','E_live_payload','B_live_routed','B_guarded']
for line in open(D+'/tables/tab_models_acc.tex'):
    for nm in names:
        if line.startswith(nm):
            v=nums(line.split('&',1)[1])
            assert len(v)==5,(nm,v)
            for c,p in zip(cells,v): chk(f'acc {nm} {c}', p, j[nm]['tolerant']['acc_mean'][c])
# prompt / routing
def table_ci(fn, cols):
    for line in open(D+'/tables/'+fn):
        for nm in names:
            if line.startswith(nm):
                cellsx=line.strip().rstrip('\\').split('&')[1:]
                for col,cell in zip(cols,cellsx):
                    v=nums(cell); assert len(v)==3,(nm,cell)
                    r=j[nm]['tolerant']['contrasts'][col]
                    chk(f'{fn} {nm} {col} diff', v[0], r['diff'])
                    chk(f'{fn} {nm} {col} lo(cluster)', v[1], r['ci95_cluster'][0], 0.0051)
                    chk(f'{fn} {nm} {col} hi(cluster)', v[2], r['ci95_cluster'][1], 0.0051)
table_ci('tab_models_prompt.tex',['E-A','B-D','B-A'])
table_ci('tab_models_routing.tex',['D-A','B-E'])
# parser table
cur=None
for line in open(D+'/tables/tab_parser_sensitivity.tex'):
    line=line.strip()
    m=re.match(r'^(Gemini low|Gemini medium|Gemini high \(1 repeat\)|GLM 5\.3 Flash|gpt-oss-120b)?\s*&\s*(tolerant|strict)\s*&(.*)',line)
    if m:
        if m.group(1): cur=m.group(1)
        rule=m.group(2); rest=m.group(3)
        v=nums(rest.split('&')[0]+'&'+'&'.join(rest.split('&')[1:5])+'&'+rest.split('&')[4]) 
        parts=[p.strip().rstrip('\\') for p in rest.split('&')]
        vals=[float(x) for x in parts[:5]]
        for c,p in zip(cells,vals): chk(f'parser {cur} {rule} {c}', p, j[cur][rule]['acc_mean'][c])
        rej=parts[5]
        mm=re.match(r'(\d+)(?: of (\d+))?',rej)
        chk(f'parser {cur} {rule} rejected', float(mm.group(1)), float(j[cur][rule]['n_invalid']), 0)
        if mm.group(2): chk(f'parser {cur} {rule} denom', float(mm.group(2)), float(j[cur][rule]['n_replies']),0)
print('checked',n,'discrepancies',len(disc))
for d in disc: print(d)
