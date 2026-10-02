"""Claim check 3: evaluated-code manifest aggregates and hash re-verification from the shipped tarball (no repository access)."""
import csv, json, hashlib, os, collections, re
S = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/ASK_supplement/v12_run'
V = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs_local/lme_final_controller_v12_qwen_180/manifest.json'
OUT = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/paper_arxiv_draft/review_claimcheck3'
rows = list(csv.DictReader(open(S + '/EVALUATED_CODE_MANIFEST.csv')))
run = json.load(open(V))['code_and_protocol_sha256']
files = {}
for root, _, fs in os.walk('/tmp/recov'):
    for f in fs:
        p = os.path.join(root, f); files[hashlib.sha256(open(p, 'rb').read()).hexdigest()] = p
res = {'rows': len(rows), 'run_manifest_entries': len(run), 'tar_files': len(files)}
res['recorded_hash_equals_run_manifest'] = sum(r['sha256_recorded_in_run_manifest'] == run[r['logical_file']] for r in rows)
res['recorded_hash_found_in_tarball_by_content'] = sum(r['sha256_recorded_in_run_manifest'] in files for r in rows)
res['reachability'] = dict(collections.Counter(r['reachability_rev_list_objects_all'] for r in rows))
res['storage_pack'] = dict(collections.Counter(r['storage_pack'] for r in rows))
res['cruft_mtime'] = dict(collections.Counter(r['cruft_object_mtime_utc'] for r in rows if r['cruft_object_mtime_utc']))
res['relation_to_baseline_same_path'] = dict(collections.Counter(r['relation_to_baseline_commit_same_path'][:60] for r in rows))
res['public_repo_contains_blob'] = dict(collections.Counter(r['public_repo_odb_contains_blob'] for r in rows))
res['reachable_scopes'] = dict(collections.Counter(r['reachable_scopes'] for r in rows))
res['oldest_commit_with_blob'] = dict(collections.Counter(r['oldest_commit_with_blob'][:50] for r in rows if r['oldest_commit_with_blob']))
orch = [r for r in rows if r['logical_file'].endswith('orchestrator.py')][0]
res['orchestrator'] = {k: orch[k] for k in ('raw_changed_lines', 'normalised_changed_lines', 'relation_to_baseline_commit_same_path')}
p = files[orch['sha256_recorded_in_run_manifest']]; res['orchestrator']['evaluated_lines'] = len(open(p).read().splitlines())
res['orchestrator']['baseline_lines'] = len(open('/tmp/ask_base/src/ask/pipeline/orchestrator.py').read().splitlines())
json.dump(res, open(OUT + '/recompute_evaluated_code.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
