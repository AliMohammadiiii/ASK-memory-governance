#!/usr/bin/env python3
"""R4b: compare the hard-coded adjudication notes in the three scripts with the notes stored in the judgments (lengths, hashes, equality, keyword-presence flags only)."""
import ast, json, sys, hashlib, glob, collections, re
RUN = sys.argv[1]
H = lambda s: hashlib.sha256(s.encode()).hexdigest()[:12]
def dict_from(path, name):
    tree = ast.parse(open(path, encoding='utf-8').read())
    for n in ast.walk(tree):
        if isinstance(n, (ast.Assign, ast.AnnAssign)):
            tgt = n.targets[0] if isinstance(n, ast.Assign) else n.target
            if isinstance(tgt, ast.Name) and tgt.id == name: return ast.literal_eval(n.value)
tg = dict_from(f'{RUN}/find_cases.py', 'TARGETS'); nine = dict_from(f'{RUN}/adjudicate_nine.py', 'ADJUDICATIONS'); gen = dict_from(f'{RUN}/adjudicate_controller_results.py', 'ADJUDICATIONS')
print('same id sets:', set(tg) == set(nine) == set(gen), 'n =', len(gen))
def jl(p): return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
top = {r['session_id']: r for r in jl(f'{RUN}/controller/judgments.jsonl')}
shard = {}
for k in range(8):
    for r in jl(f'{RUN}/controller/_shard{k}/judgments.jsonl'): shard[r['session_id']] = (k, r)
# keyword-presence flags were dropped from the outputs; retained list unused
vocab = ['preference', 'rubric', 'gold', 'reference', 'expected', 'acceptable', 'equivalent', 'format', 'paraphrase', 'date', 'unit', 'strict', 'lenient', 'semantic', 'personal', 'recommend', 'mention', 'ground', 'correct', 'incorrect', 'judge']
rows = []
for q in gen:
    k, s = shard[q]; t = top[q]
    note = gen[q]
    rows.append(dict(id=q, shard=k, competency=s['competency'], len_find_cases_reason=len(tg[q]), len_nine_note=len(nine[q]), len_generic_note=len(note),
        stored_note_equals_generic=(s.get('adjudication_note') == note and t.get('adjudication_note') == note), stored_note_equals_nine=(s.get('adjudication_note') == nine[q]),
        nine_equals_generic=(nine[q] == note), find_reason_equals_nine=(tg[q] == nine[q]),
        topfile_pre_rationale_equals_nine_note=(t.get('judge_rationale_pre_adjudication') == nine[q]), shard_pre_rationale_equals_nine_note=(s.get('judge_rationale_pre_adjudication') == nine[q]),
        pre_correct=s.get('correct_pre_adjudication'), pre_score=s.get('judge_score_pre_adjudication'), judge_was_called=s.get('judge_was_called'), used_scoring_fallback=s.get('used_scoring_fallback'),
        pre_raw_output_present=('judge_raw_output_pre_adjudication' in s)))
for r in rows: print(r)
json.dump(rows, open('handoff/r4_note_check.json', 'w'))
# which cache entries
for k in range(8):
    p = f'{RUN}/controller/_shard{k}/judge_cache.jsonl'
    n = sum(1 for l in open(p, encoding='utf-8') if 'correct_pre_adjudication' in l)
    print('shard', k, 'judge_cache adjudicated entries', n, 'adjudicated judgments', sum(1 for q, (kk, r) in shard.items() if kk == k and r.get('adjudicated')))
