"""Claim check 3: rebuild the four-cell prompts with the baseline builders and compare character counts with reported prompt_tokens (approximate; no model tokenizer available)."""
import sys, json, hashlib, collections, importlib, statistics
sys.dont_write_bytecode = True
sys.path.insert(0, '/tmp/ask_base_src')
m = importlib.import_module('ask.eval.mgp6_v43')
R = '/Users/alimohammadi/Workspace/research/ASK-memory-governance'
S = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/ASK_supplement/substitute_runs/'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3/'
CFG = R + '/configs/experiments/mgp6_v43/'
recs = m.load_public_records(R + '/benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl'); byid = {r.public_id: r for r in recs}
zero = open(CFG + 'decision_system_prompt.txt', encoding='utf-8').read(); live = open(CFG + 'live_model_controller_prompt.txt', encoding='utf-8').read()
CELLS = {'A_zero_payload': lambda r: m.build_system_prompt(r, 'decision_zero_shot', zero), 'B_live_routed': lambda r: m.build_system_prompt(r, 'live_model_controller', live),
         'D_zero_routed': lambda r: m.build_system_prompt(r, 'live_model_controller', zero), 'E_live_payload': lambda r: m.build_system_prompt(r, 'decision_zero_shot', live)}
prompts = {(i, c): f(byid[i]) for c, f in CELLS.items() for i in byid}
res = {'prompt_hash_match': {}, 'gap': {}}
for run in ['gemini_low', 'gemini_medium', 'gemini_high', 'glm_5.3_flash', 'gpt_oss_120b_medium']:
    rows = [json.loads(l) for l in open(S + run + '/results.jsonl')]
    rows = [r for r in rows if r.get('action') != 'FAILED']
    ok = sum(hashlib.sha256(prompts[(r['public_id'], r['cell'])].encode()).hexdigest() == r['prompt_sha256'] for r in rows)
    res['prompt_hash_match'][run] = [ok, len(rows)]
    gaps = collections.defaultdict(list); ratios = collections.defaultdict(list)
    for r in rows:
        u = r.get('usage') or {}
        pt = u.get('prompt_tokens') if isinstance(u, dict) else None
        if pt: gaps[r['cell']].append(pt - len(prompts[(r['public_id'], r['cell'])]) / 4.0); ratios[r['cell']].append(pt / len(prompts[(r['public_id'], r['cell'])]))
    res['gap'][run] = {c: {'mean_gap_tokens_vs_chars_div4': round(statistics.mean(v), 0), 'mean_tokens_per_char': round(statistics.mean(ratios[c]), 3)} for c, v in gaps.items()}
res['prompt_chars_mean'] = {c: round(statistics.mean(len(prompts[(i, c)]) for i in byid)) for c in CELLS}
json.dump(res, open(OUT + 'prompt_token_gap.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
