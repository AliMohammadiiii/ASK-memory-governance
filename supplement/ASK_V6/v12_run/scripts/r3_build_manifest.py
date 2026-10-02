#!/usr/bin/env python3
"""R3: EVALUATED_CODE_MANIFEST.csv and evaluated_vs_baseline_diffs/. Read-only git access to the backup repository and the audit baseline repository."""
import json, subprocess, os, re, csv, hashlib, shutil, tempfile, collections
BK = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance'
PUB = '/Users/alimohammadi/Workspace/research/ASK-memory-governance'
BASE = 'f6bf66e4766d769727edf6b42c76b9977b14978a'
RUN_HEAD = 'a284b2efcf947bf69f7456ea87348059594f26da'
RUN = BK + '/runs_local/lme_final_controller_v12_qwen_180'
REC = '/Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/phase15_v12_raw_evidence/recovered_evaluated_code'
env = dict(os.environ, HOME='/tmp', GIT_CONFIG_GLOBAL='/dev/null')
def git(repo, *a, check=True):
    r = subprocess.run(['git', '-c', 'safe.directory=*', '-C', repo, *a], capture_output=True, env=env)
    if check and r.returncode != 0: raise RuntimeError((a, r.stderr[:200]))
    return r.stdout, r.returncode

def commits_at_path(path, oid):
    outc, _ = git(BK, 'log', '--all', '--format=%H %aI', '--', path)
    hits = []
    for l in outc.decode().strip().split('\n'):
        if not l.strip(): continue
        c, dt = l.split()
        o, rc = git(BK, 'rev-parse', f'{c}:{path}', check=False)
        if rc == 0 and o.decode().strip() == oid: hits.append(f'{c[:10]} {dt[:10]}')
    return ';'.join(hits[::-1])

man = json.load(open(RUN + '/manifest.json'))['code_and_protocol_sha256']
dm = json.load(open(PUB + '/artifacts/manifests/lme_v12_derived_manifest.json'))['code_identity']['historical_code_and_protocol_sha256']
blobs = json.load(open('handoff/r3_blobs.json'))['blobs']; packs = json.load(open('handoff/r3_packs.json'))
def norm(t):
    t = t.replace('\r\n', '\n')
    t = t.replace('ksa', 'ask').replace('KSA', 'ASK').replace('Ksa', 'Ask')
    return '\n'.join(l.rstrip() for l in t.split('\n'))
def numstat_diff(a_text, b_text, path, label_a, label_b, keep_diff):
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(f'{td}/a/{os.path.dirname(path)}', exist_ok=True); os.makedirs(f'{td}/b/{os.path.dirname(path)}', exist_ok=True)
        open(f'{td}/a/{path}', 'w', encoding='utf-8', newline='').write(a_text); open(f'{td}/b/{path}', 'w', encoding='utf-8', newline='').write(b_text)
        r = subprocess.run(['git', 'diff', '--no-index', '--no-color', '--minimal', '-U3', f'a/{path}', f'b/{path}'], cwd=td, capture_output=True, env=env)
        d = r.stdout.decode('utf-8', 'replace')
        add = sum(1 for l in d.split('\n') if l.startswith('+') and not l.startswith('+++')); dele = sum(1 for l in d.split('\n') if l.startswith('-') and not l.startswith('---'))
        hunks = sum(1 for l in d.split('\n') if l.startswith('@@'))
        if keep_diff:
            lines = d.split('\n')
            body = [l for l in lines if not l.startswith('diff --git') and not l.startswith('index ') and not l.startswith('--- ') and not l.startswith('+++ ')]
            d = f'--- {label_a}\n+++ {label_b}\n' + '\n'.join(body)
        return add, dele, hunks, d
rows = []; diffs = []
base_tree = set(git(PUB, 'ls-tree', '-r', '--name-only', BASE)[0].decode().split('\n'))
for path, hs in man.items():
    b = blobs[path]; oid = b['blob']
    ev_text = git(BK, 'cat-file', 'blob', oid)[0]
    sha_ok = hashlib.sha256(ev_text).hexdigest() == hs
    rec_name = path.replace('/', '__'); rec_ok = os.path.exists(f'{REC}/{rec_name}') and hashlib.sha256(open(f'{REC}/{rec_name}', 'rb').read()).hexdigest() == hs
    # baseline commit
    out, rc = git(PUB, 'cat-file', 'blob', f'{BASE}:{path}', check=False)
    reloc = ''; cmp_path = path; cmp_add = cmp_del = cmp_nadd = cmp_ndel = ''
    if rc != 0:
        rel = 'absent at same path'; base_blob = ''; add = dele = nadd = ndel = hunks = ''; alt = [p for p in base_tree if os.path.basename(p) == os.path.basename(path)]
        if len(alt) == 1:
            out_alt, _ = git(PUB, 'cat-file', 'blob', f'{BASE}:{alt[0]}'); ab = git(PUB, 'rev-parse', f'{BASE}:{alt[0]}')[0].decode().strip()
            if ab == oid: reloc = f'identical to baseline-commit {alt[0]}'; cmp_path = alt[0]; cmp_add = cmp_del = cmp_nadd = cmp_ndel = 0
            else:
                t_e = ev_text.decode('utf-8', 'replace'); t_b = out_alt.decode('utf-8', 'replace')
                a_, d_, h_, dd = numstat_diff(t_e, t_b, path, f'evaluated:{path} (git blob {oid}, sha256 {hs[:12]})', f'baseline-commit {BASE[:12]}:{alt[0]} (git blob {ab}) [relocated path]', True)
                na_, nd_, _, _ = numstat_diff(norm(t_e), norm(t_b), path, '', '', False)
                cmp_path = alt[0]; cmp_add, cmp_del, cmp_nadd, cmp_ndel = a_, d_, na_, nd_
                reloc = f'differs from baseline-commit {alt[0]} (raw {a_} added / {d_} deleted baseline-side; normalised {na_}/{nd_})'
                diffs.append((path + ' [vs ' + alt[0] + ']', dd, a_, d_, h_, na_, nd_, len(t_e.splitlines()), len(t_b.splitlines())))
        else: reloc = 'no single relocated candidate'
    else:
        base_blob = git(PUB, 'rev-parse', f'{BASE}:{path}')[0].decode().strip(); alt = []
        if base_blob == oid: rel = 'identical'; add = dele = nadd = ndel = hunks = 0; cmp_add = cmp_del = cmp_nadd = cmp_ndel = 0
        else:
            t_e = ev_text.decode('utf-8', 'replace'); t_b = out.decode('utf-8', 'replace')
            add, dele, hunks, d = numstat_diff(t_e, t_b, path, f'evaluated:{path} (git blob {oid}, sha256 {hs[:12]})', f'baseline-commit {BASE[:12]}:{path} (git blob {base_blob})', True)
            nadd, ndel, nh, _ = numstat_diff(norm(t_e), norm(t_b), path, '', '', False)
            rel = f'differs (raw {add} added / {dele} deleted baseline-side; normalised {nadd}/{ndel})'; cmp_add, cmp_del, cmp_nadd, cmp_ndel = add, dele, nadd, ndel
            diffs.append((path, d, add, dele, hunks, nadd, ndel, len(t_e.splitlines()), len(t_b.splitlines())))
    # recorded run git_head
    era_path = path.replace('src/ask/', 'src/ksa/', 1) if path.startswith('src/ask/') else path
    out2, rc2 = git(BK, 'cat-file', 'blob', f'{RUN_HEAD}:{era_path}', check=False)
    if rc2 != 0: head_rel = f'absent at run git_head ({era_path})'
    else:
        hb = git(BK, 'rev-parse', f'{RUN_HEAD}:{era_path}')[0].decode().strip()
        if hb == oid: head_rel = f'identical to run git_head blob at {era_path}'
        else:
            t_e = ev_text.decode('utf-8', 'replace'); t_h = out2.decode('utf-8', 'replace')
            ha, hd, _, _ = numstat_diff(norm(t_e), norm(t_h), path, '', '', False)
            head_rel = f'differs from run git_head blob at {era_path}: content differs from the recorded git_head version, consistent with git_dirty_at_start=true (normalised {hd} lines only in evaluated, {ha} only in git_head)'
    reach = 'reachable' if b['in_rev_list_objects_all'] else 'UNREFERENCED'
    scopes = ','.join(n for n, k in (('branches', 'in_branches'), ('remotes', 'in_remotes'), ('tags', 'in_tags'), ('stash', 'in_stash'), ('codex_checkpoint_trees', 'in_codex_checkpoint_trees'), ('reflog', 'in_reflog_closure')) if b.get(k))
    pk = packs[path]
    rows.append(dict(logical_file=path, sha256_recorded_in_run_manifest=hs, sha256_of_recovered_blob_matches=sha_ok, sha256_matches_derived_manifest_entry=(dm.get(path) == hs), git_blob_id=oid, blob_bytes=b['size'],
        reachability_rev_list_objects_all=reach, reachable_scopes=scopes, n_commits_adding_or_removing_blob=len(b['pickaxe_commits']), oldest_commit_with_blob=(b['pickaxe_commits'][-1].split()[0] if b['pickaxe_commits'] else ''),
        storage_pack=pk['pack'][:12] + ('(cruft)' if pk['is_cruft_pack'] else ''), cruft_object_mtime_utc=pk['object_mtime_utc'] or '',
        source_location=f'backup repository object store, {"cruft pack" if pk["is_cruft_pack"] else "regular pack"} {pk["pack"][:12]}; flattened copy in phase15_v12_raw_evidence/recovered_evaluated_code/{rec_name}',
        recovered_copy_in_phase15_hash_verified=rec_ok, relation_to_run_manifest_hash_entry='content SHA-256 equals the manifest value' if sha_ok else 'MISMATCH',
        relation_to_run_git_head_a284b2ef=head_rel, relation_to_baseline_commit_same_path=rel, baseline_commit_blob_id=base_blob, compared_baseline_path=cmp_path, raw_lines_only_in_evaluated=cmp_del, raw_lines_only_in_baseline=cmp_add, raw_changed_lines=(cmp_add + cmp_del if cmp_add != '' else ''), normalised_lines_only_in_evaluated=cmp_ndel, normalised_lines_only_in_baseline=cmp_nadd, normalised_changed_lines=(cmp_nadd + cmp_ndel if cmp_nadd != '' else ''), baseline_candidate_paths_by_basename=';'.join(sorted(alt)), relation_to_relocated_baseline_path=reloc, commits_containing_blob_at_path=commits_at_path(path, oid),
        public_repo_odb_contains_blob=(git(PUB, 'cat-file', '-e', oid, check=False)[1] == 0)))
# diffs, orchestrator first
diffs.sort(key=lambda x: (0 if x[0] == 'src/ask/pipeline/orchestrator.py' else 1, -(x[5] + x[6])))
shutil.rmtree('evaluated_vs_baseline_diffs', ignore_errors=True); os.makedirs('evaluated_vs_baseline_diffs')
idx = [['order', 'file', 'diff_file', 'evaluated_lines', 'baseline_lines', 'raw_deleted_evaluated_side', 'raw_added_baseline_side', 'raw_changed_lines', 'normalised_deleted', 'normalised_added', 'normalised_changed_lines', 'hunks_raw']]
for i, (path, d, add, dele, hunks, nadd, ndel, le, lb) in enumerate(diffs, 1):
    fn = f'{i:02d}_' + re.sub(r'[^A-Za-z0-9_.-]', '_', path.replace('/', '__')) + '.diff'
    hdr = (f'# Unified diff, direction: evaluated version (minus lines) to baseline-commit version (plus lines).\n# file: {path}\n# raw changed lines (deleted+added): {dele + add} (deleted {dele}, added {add}); hunks {hunks}\n'
           f'# normalised changed lines (rename ksa->ask, CRLF->LF, trailing whitespace stripped): {ndel + nadd} (deleted {ndel}, added {nadd})\n')
    open(f'evaluated_vs_baseline_diffs/{fn}', 'w', encoding='utf-8').write(hdr + d + '\n')
    idx.append([i, path, fn, le, lb, dele, add, dele + add, ndel, nadd, ndel + nadd, hunks])
with open('evaluated_vs_baseline_diffs/INDEX.csv', 'w', newline='') as f: csv.writer(f).writerows(idx)
with open('EVALUATED_CODE_MANIFEST.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(len(rows), 'manifest rows;', len(diffs), 'diffs')
c = collections.Counter(r['relation_to_baseline_commit_same_path'].split(' (')[0] for r in rows); print(dict(c))
print(collections.Counter(r['reachability_rev_list_objects_all'] for r in rows))
for r in idx[1:]: print(r[0], r[1], 'norm', r[10], 'raw', r[7])
for r in rows:
    if r['relation_to_baseline_commit_same_path'].startswith('absent'): print('ABSENT', r['logical_file'], r['baseline_candidate_paths_by_basename'])
print('head rel', collections.Counter(r['relation_to_run_git_head_a284b2ef'] for r in rows))
print('sha ok', all(r['sha256_of_recovered_blob_matches'] for r in rows), 'rec ok', all(r['recovered_copy_in_phase15_hash_verified'] for r in rows), 'derived ok', all(r['sha256_matches_derived_manifest_entry'] for r in rows))
