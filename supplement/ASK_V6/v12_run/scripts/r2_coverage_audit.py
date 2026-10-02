#!/usr/bin/env python3
"""R2 coverage audit of the V12 controller run. Reads ids, booleans and hashes only (no answer, gold, question or judge text is printed or written)."""
import json, sys, hashlib, csv, collections, os
RUN = sys.argv[1]
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for ch in iter(lambda: f.read(1 << 20), b''): h.update(ch)
    return h.hexdigest()
def jl(p):
    with open(p, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]
ev = json.load(open('handoff/shard_log_events.json'))
manifest = json.load(open(f'{RUN}/manifest.json'))
# 1. expected ordered ids reconstructed from shard progress logs (Q_DONE order, slice position = shard + 8*j)
pos_id = {}
shard_ids = {}
for k in range(8):
    ids = []
    for typ, ln, d in ev[str(k)]['events']:
        if typ == 'Q_DONE' and d['q'] not in ids: ids.append(d['q'])
    shard_ids[k] = ids
    for j, q in enumerate(ids): pos_id[k + 8 * j] = q
ordered = [pos_id[i] for i in range(len(pos_id))]
assert sorted(pos_id) == list(range(180)), 'positions not contiguous'
h_ordered = hashlib.sha256('\n'.join(ordered).encode()).hexdigest()
h_sorted = hashlib.sha256('\n'.join(sorted(ordered)).encode()).hexdigest()
res = dict(expected_ids=dict(n=len(ordered), n_distinct=len(set(ordered)), sha256_ordered_join_newline=h_ordered, sha256_sorted_join_newline=h_sorted, manifest_evaluated_session_ids_sha256=manifest['evaluated_session_ids_sha256'],
           ordered_hash_matches_manifest=(h_ordered == manifest['evaluated_session_ids_sha256']), sorted_hash_matches_manifest=(h_sorted == manifest['evaluated_session_ids_sha256']),
           source='reconstructed from per-shard progress logs (Q_DONE order, round-robin shard = position mod 8); slice file not opened'))
exp = set(ordered); exp_shard = {q: pos % 8 for pos, q in pos_id.items()}; exp_pos = {q: pos for pos, q in pos_id.items()}
# 2. merged artifacts
art = {}
for name in ('predictions.jsonl', 'answers.jsonl', 'judgments.jsonl'):
    p = f'{RUN}/controller/{name}'; rows = jl(p); ids = [r['session_id'] for r in rows]; c = collections.Counter(ids)
    art[name] = dict(path=f'controller/{name}', sha256=sha(p), bytes=os.path.getsize(p), n_rows=len(rows), n_distinct_ids=len(c), n_duplicate_ids=sum(1 for v in c.values() if v > 1), missing_expected=sorted(exp - set(ids)), unexpected=sorted(set(ids) - exp), ordered_as_expected=(ids == ordered))
rep_p = f'{RUN}/controller/report.json'; rep = json.load(open(rep_p))
art['report.json'] = dict(path='controller/report.json', sha256=sha(rep_p), bytes=os.path.getsize(rep_p), n_sessions=rep['n_sessions'], answerable_n=rep['answerable_n'], abstention_n=rep['abstention_n'], sum_competency_n=sum(r['n'] for r in rep['rows']),
                          competency_n={r['competency']: r['n'] for r in rep['rows']}, overall_accuracy=rep['overall_accuracy'], contains_per_question_ids=False)
for name in ('results.md', 'action_log.jsonl', 'extraction_cache.jsonl', 'extraction_trace.jsonl', 'relation_cache.jsonl', 'relation_trace.jsonl', 'judge_cache.jsonl'):
    p = f'{RUN}/controller/{name}'
    art[name] = dict(path=f'controller/{name}', sha256=sha(p), bytes=os.path.getsize(p))
art['predictions_equals_answers_bytes'] = (art['predictions.jsonl']['sha256'] == art['answers.jsonl']['sha256'])
res['merged_artifacts'] = art
# 3. per-shard files: origin of each id and comparison with merged
origin = {}
shard_info = {}
for k in range(8):
    d = f'{RUN}/controller/_shard{k}'
    info = {}
    for name in ('answers.jsonl', 'predictions.jsonl', 'judgments.jsonl'):
        rows = jl(f'{d}/{name}'); ids = [r['session_id'] for r in rows]
        info[name] = dict(n_rows=len(rows), n_distinct=len(set(ids)), dup=len(ids) - len(set(ids)), ids_match_expected_round_robin=(ids == shard_ids[k]), sha256=sha(f'{d}/{name}'))
        if name == 'judgments.jsonl':
            for q in ids: origin.setdefault(q, []).append(k)
    for nm in ('judgments.jsonl.pre_manual_adjudication.orig',):
        if os.path.exists(f'{d}/{nm}'):
            rows = jl(f'{d}/{nm}'); ids = [r['session_id'] for r in rows]
            info['judgments_orig'] = dict(n_rows=len(rows), n_distinct=len(set(ids)), same_id_set_as_current=(set(ids) == {r['session_id'] for r in jl(f'{d}/judgments.jsonl')}), sha256=sha(f'{d}/{nm}'))
        else: info['judgments_orig'] = None
    info['report_n_sessions'] = json.load(open(f'{d}/report.json'))['n_sessions']
    shard_info[k] = info
res['shards'] = shard_info
# merged vs concatenation of shard rows (parsed equality, order)
for name in ('answers.jsonl', 'predictions.jsonl', 'judgments.jsonl'):
    cat = []
    for k in range(8): cat += jl(f'{RUN}/controller/_shard{k}/{name}')
    merged = jl(f'{RUN}/controller/{name}')
    res['merged_artifacts'][name]['equals_shard_concatenation_parsed'] = (cat == merged)
    res['merged_artifacts'][name]['equals_shard_concatenation_parsed_ignoring_order'] = (sorted(json.dumps(r, sort_keys=True) for r in cat) == sorted(json.dumps(r, sort_keys=True) for r in merged))
res['origin_multiplicity'] = dict(collections.Counter(len(v) for v in origin.values()))
res['origin_matches_round_robin'] = all(origin[q] == [exp_shard[q]] for q in exp)
# baselines b1..b4 coverage
bl = {}
for b in ('b1', 'b2', 'b3', 'b4'):
    p = f'{RUN}/{b}/judgments.jsonl'; ids = [r['session_id'] for r in jl(p)]
    bl[b] = dict(sha256=sha(p), n_rows=len(ids), n_distinct=len(set(ids)), same_set_as_expected=(set(ids) == exp), missing=len(exp - set(ids)))
res['baseline_judgment_coverage'] = bl
# id table
with open('COVERAGE_ID_TABLE.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['slice_position', 'question_id', 'expected_shard_round_robin', 'in_predictions', 'in_answers', 'in_judgments', 'multiplicity_predictions', 'multiplicity_judgments', 'source_shard_files_judgments', 'in_b1', 'in_b2', 'in_b3', 'in_b4'])
    pc = collections.Counter(r['session_id'] for r in jl(f'{RUN}/controller/predictions.jsonl')); ac = collections.Counter(r['session_id'] for r in jl(f'{RUN}/controller/answers.jsonl')); jc = collections.Counter(r['session_id'] for r in jl(f'{RUN}/controller/judgments.jsonl'))
    bsets = {b: {r['session_id'] for r in jl(f'{RUN}/{b}/judgments.jsonl')} for b in ('b1', 'b2', 'b3', 'b4')}
    for i, q in enumerate(ordered):
        w.writerow([i, q, exp_shard[q], int(pc[q] > 0), int(ac[q] > 0), int(jc[q] > 0), pc[q], jc[q], ';'.join(map(str, origin.get(q, []))), *[int(q in bsets[b]) for b in ('b1', 'b2', 'b3', 'b4')]])
json.dump(res, open('COVERAGE_AUDIT.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ('shards',)}, indent=1)[:5000])
