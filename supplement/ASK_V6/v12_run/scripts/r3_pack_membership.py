#!/usr/bin/env python3
"""Which pack holds each evaluated blob; cruft-pack object mtimes for unreachable blobs (read-only parse of .idx/.mtimes)."""
import json, subprocess, os, struct, datetime, glob, sys
B = '/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance'
env = dict(os.environ, HOME='/tmp', GIT_CONFIG_GLOBAL='/dev/null')
d = json.load(open('handoff/r3_blobs.json'))
blobs = {v['blob']: n for n, v in d['blobs'].items()}
packs = sorted(glob.glob(f'{B}/.git/objects/pack/pack-*.idx'))
out = {}
for idx in packs:
    pk = os.path.basename(idx)[5:-4]
    r = subprocess.run(['git', '-c', 'safe.directory=*', 'show-index'], stdin=open(idx, 'rb'), capture_output=True, env=env)
    oids = [l.split()[1] for l in r.stdout.decode().strip().split('\n')]   # sorted by oid
    mt = idx[:-4] + '.mtimes'
    times = None
    if os.path.exists(mt):
        data = open(mt, 'rb').read()
        assert data[:4] == b'MTME', data[:4]
        ver, hid = struct.unpack('>II', data[4:12])
        n = len(oids)
        times = struct.unpack('>%dI' % n, data[12:12 + 4 * n])
    pos = {o: i for i, o in enumerate(oids)}
    for b, name in blobs.items():
        if b in pos:
            out[name] = dict(blob=b, pack=pk, is_cruft_pack=times is not None, object_mtime_utc=(datetime.datetime.fromtimestamp(times[pos[b]], datetime.timezone.utc).isoformat() if times else None))
    print(pk[:12], 'objects', len(oids), 'cruft' if times else 'normal')
json.dump(out, open('handoff/r3_packs.json', 'w'), indent=1)
for n, v in out.items(): print(n, v['blob'][:10], v['pack'][:10], v['is_cruft_pack'], v['object_mtime_utc'])
