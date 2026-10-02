#!/usr/bin/env python3
"""R4a: baseline judgment overrides in b1 and b4 (ids, verdict booleans, counts, field locations). No text fields are printed or written; rationale text is represented by length and a hash prefix."""
import json, sys, csv, hashlib, glob, os, collections
RUN = sys.argv[1]
def jl(p): return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
H = lambda s: hashlib.sha256(str(s).encode()).hexdigest()[:12]
out_rows = []; summary = {}
for b in ('b1', 'b2', 'b3', 'b4'):
    top = jl(f'{RUN}/{b}/judgments.jsonl'); rep = json.load(open(f'{RUN}/{b}/report.json'))
    shard_of = {}; shard_rows = {}
    for p in sorted(glob.glob(f'{RUN}/{b}/_shard*/judgments.jsonl')):
        k = int(p.split('_shard')[1].split('/')[0])
        for r in jl(p): shard_of[r['session_id']] = k; shard_rows[r['session_id']] = r
    ov = [r for r in top if r.get('judge_overridden')]
    now = sum(1 for r in top if r['correct'])
    orig = sum(1 for r in top if (r['judge_original_correct'] if r.get('judge_overridden') else r['correct']))
    summary[b] = dict(n=len(top), n_shard_dirs=len(set(shard_of.values())), correct_as_stored=now, correct_before_override=orig, n_overridden=len(ov), report_overall_accuracy=rep['overall_accuracy'], report_correct_implied=round(rep['overall_accuracy'] * rep['n_sessions']),
                      report_n=rep['n_sessions'], judgments_sha256=hashlib.sha256(open(f'{RUN}/{b}/judgments.jsonl', 'rb').read()).hexdigest(), n_judge_called=sum(1 for r in top if r.get('judge_was_called')) if 'judge_was_called' in top[0] else None,
                      schema_has_judge_was_called=('judge_was_called' in top[0]))
    comp_before = collections.Counter(); comp_after = collections.Counter()
    for r in top:
        comp_after[r['competency']] += bool(r['correct'])
        comp_before[r['competency']] += bool(r['judge_original_correct'] if r.get('judge_overridden') else r['correct'])
    summary[b]['competency_correct_after'] = dict(comp_after); summary[b]['competency_correct_before'] = dict(comp_before)
    summary[b]['report_competency_acc_x_n'] = {x['competency']: round(x['accuracy'] * x['n']) for x in rep['rows']}
    for r in ov:
        sr = shard_rows.get(r['session_id'], {})
        extra = sorted(set(r) - set(top[0]) if False else [k for k in r if k.startswith('judge_original') or k == 'judge_overridden'])
        out_rows.append(dict(system=b, shard_dir=f'{b}/_shard{shard_of.get(r["session_id"])}', item_id=r['session_id'], competency=r['competency'], original_verdict_correct=r['judge_original_correct'], overridden_verdict_correct=r['correct'], judge_overridden_value=r['judge_overridden'],
            direction=('correct_to_incorrect' if r['judge_original_correct'] and not r['correct'] else 'incorrect_to_correct'),
            override_fields_in_merged_judgments=True, override_fields_in_shard_judgments=bool(sr.get('judge_overridden')), merged_equals_shard_row=(sr == r),
            original_rationale_len=len(r['judge_original_rationale'] or ''), original_rationale_sha256_12=H(r['judge_original_rationale']), current_rationale_len=len(r.get('judge_rationale') or ''), current_rationale_sha256_12=H(r.get('judge_rationale')),
            judge_model_id=r.get('judge_model_id'), judge_score=r.get('judge_score'), judge_was_called=r.get('judge_was_called', 'field_absent'), fields_present=';'.join(k for k in r if k.startswith('judge_original') or k == 'judge_overridden' or k == 'adjudicated')))
json.dump(summary, open('handoff/r4_baseline_summary.json', 'w'), indent=1)
with open('BASELINE_OVERRIDES_TABLE.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys())); w.writeheader(); w.writerows(out_rows)
print(json.dumps({b: {k: v for k, v in s.items() if k not in ('judgments_sha256',)} for b, s in summary.items()}, indent=1)[:4500])
for r in out_rows: print({k: r[k] for k in ('system', 'shard_dir', 'item_id', 'competency', 'original_verdict_correct', 'overridden_verdict_correct', 'merged_equals_shard_row', 'original_rationale_len', 'current_rationale_len', 'judge_was_called')})
