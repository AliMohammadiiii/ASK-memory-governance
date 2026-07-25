#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, sys, tempfile, zipfile
from pathlib import Path

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def verify_manifest(root):
    manifest=json.loads((root/"MANIFEST.json").read_text(encoding="utf-8"))
    listed={row["relative_path"]:row for row in manifest["files"]}
    actual={p.relative_to(root).as_posix():p for p in root.rglob("*") if p.is_file() and p.name!="MANIFEST.json"}
    assert set(listed)==set(actual),(set(actual)-set(listed),set(listed)-set(actual))
    assert manifest["file_count_excluding_manifest"]==len(actual)
    for rel,p in actual.items():
        assert sha(p)==listed[rel]["sha256"],rel
        assert p.stat().st_size==listed[rel]["size_bytes"],rel

def main(root):
    root=Path(root); readiness=json.loads((root/"FINAL_RELEASE_READINESS.json").read_text(encoding="utf-8"))
    for name,meta in readiness["output_archives"].items():
        path=root/meta["filename"]; assert sha(path)==meta["sha256"],name
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None,name
            with tempfile.TemporaryDirectory() as tmp:
                z.extractall(tmp); verify_manifest(Path(tmp))
    print(json.dumps({"verified":True,"archive_count":len(readiness["output_archives"])},indent=2))
if __name__=="__main__": main(sys.argv[1] if len(sys.argv)>1 else ".")
