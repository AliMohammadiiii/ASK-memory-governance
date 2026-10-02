#!/usr/bin/env python3
"""R3 step 1: independently identify the git blob for each of the 17 recorded SHA-256 values in the backup repository's object store (read-only git plumbing),
and compute reachability under several scopes. Writes handoff/r3_blobs.json."""
import json, subprocess, hashlib, os, sys, collections
B = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance'
RUN = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance/runs_local/lme_final_controller_v12_qwen_180'
env = dict(os.environ, HOME='/tmp', GIT_CONFIG_GLOBAL='/dev/null')
def git(*a, inp=None, text=True):
    r = subprocess.run(['git', '-c', 'safe.directory=*', '-C', B, *a], capture_output=True, env=env, input=inp)
    if r.returncode not in (0,): raise RuntimeError((a, r.stderr[:300]))
    return r.stdout.decode('utf-8', 'replace') if text else r.stdout
manifest = json.load(open(f'{RUN}/manifest.json'))['code_and_protocol_sha256']
want = {v: k for k, v in manifest.items()}
# all blobs with sha256
allobj = git('cat-file', '--batch-all-objects', '--batch-check').strip().split('\n')
blobs = [(l.split()[0], int(l.split()[2])) for l in allobj if l.split()[1] == 'blob']
print('objects', len(allobj), 'blobs', len(blobs))
# stream all blob contents
p = subprocess.Popen(['git', '-c', 'safe.directory=*', '-C', B, 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env)
found = collections.defaultdict(list)
def read_obj(oid):
    p.stdin.write((oid + '\n').encode()); p.stdin.flush()
    hdr = p.stdout.readline().decode().split()
    size = int(hdr[2]); data = p.stdout.read(size); p.stdout.read(1)
    return data
for oid, sz in blobs:
    data = read_obj(oid)
    hs = hashlib.sha256(data).hexdigest()
    if hs in want: found[hs].append((oid, sz))
p.stdin.close(); p.wait()
print('matched sha256 values', len(found), 'of', len(want), {k[:8]: v for k, v in found.items()})
# reachability scopes
def objset(*args):
    s = set()
    for l in git('rev-list', '--objects', *args).split('\n'):
        if l.strip(): s.add(l.split()[0])
    return s
S_all = objset('--all')
S_branches = objset('--branches')
S_remotes = objset('--remotes')
S_tags = objset('--tags')
S_stash = objset('refs/stash')
codex_refs = [l.split()[2] for l in git('for-each-ref').strip().split('\n') if l.split()[2].startswith('refs/codex/')]
S_codex = set()
for r in codex_refs: S_codex |= objset(r)
S_head = objset('HEAD')
S_reflog = objset('--reflog')
S_commits_refs = S_branches | S_remotes | S_tags
res = {}
for hs, name in want.items():
    oids = found.get(hs, [])
    if not oids: res[name] = dict(sha256=hs, blob=None); continue
    oid = oids[0][0]
    # commits that add/remove this blob (pickaxe), all refs
    log = git('log', '--all', '--format=%H %aI', f'--find-object={oid}').strip().split('\n')
    log = [l for l in log if l.strip()]
    res[name] = dict(sha256=hs, blob=oid, size=oids[0][1], n_blob_ids_for_content=len(oids),
        in_rev_list_objects_all=oid in S_all, in_branches=oid in S_branches, in_remotes=oid in S_remotes, in_tags=oid in S_tags, in_stash=oid in S_stash, in_codex_checkpoint_trees=oid in S_codex, in_HEAD=oid in S_head,
        in_reflog_closure=oid in S_reflog, pickaxe_commits=log)
# storage form
loose = set()
for d in os.listdir(f'{B}/.git/objects'):
    if len(d) == 2 and os.path.isdir(f'{B}/.git/objects/{d}'):
        for f in os.listdir(f'{B}/.git/objects/{d}'): loose.add(d + f)
for name, v in res.items():
    if v.get('blob'): v['storage'] = 'loose' if v['blob'] in loose else 'packed'
json.dump(dict(blobs=res, n_all_objects=len(allobj), n_loose=len(loose), codex_refs=len(codex_refs), n_S_all=len(S_all)), open('handoff/r3_blobs.json', 'w'), indent=1)
for name, v in res.items(): print(name, v.get('blob', None) and v['blob'][:10], 'all', v.get('in_rev_list_objects_all'), 'br', v.get('in_branches'), 'rem', v.get('in_remotes'), 'tag', v.get('in_tags'), 'stash', v.get('in_stash'), 'codex', v.get('in_codex_checkpoint_trees'), 'reflog', v.get('in_reflog_closure'), v.get('storage'), 'pickaxe', len(v.get('pickaxe_commits', [])))
