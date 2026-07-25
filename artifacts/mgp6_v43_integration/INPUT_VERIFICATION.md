# MGP-6 v4.3 input verification

**Result:** PASS. Verification was performed outside the repository at
`/tmp/mgp6_v43_handoff.jDCt7p`; no release asset was copied into the worktree.

## Commands executed

```bash
unzip -q /Users/ali/Downloads/MGP6_v4.3_CODEX_PAPER_THESIS_TEST_HANDOFF.zip -d /tmp/mgp6_v43_handoff.jDCt7p
(cd /tmp/mgp6_v43_handoff.jDCt7p && python3 verify_handoff.py)
unzip -q /tmp/mgp6_v43_handoff.jDCt7p/release/MGP-6-v4.3.0-human-validated-final-BUNDLE.zip -d /tmp/mgp6_v43_handoff.jDCt7p/release_extract
(cd /tmp/mgp6_v43_handoff.jDCt7p/release_extract && python3 verify_release.py .)
unzip -t /Users/ali/Downloads/MGP6_v4.3_CODEX_PAPER_THESIS_TEST_HANDOFF.zip
unzip -t /tmp/mgp6_v43_handoff.jDCt7p/release/MGP-6-v4.3.0-human-validated-final-BUNDLE.zip
```

## Exact verifier output

```json
{
  "verified": true,
  "bundle": "MGP-6-v4.3.0-human-validated-final-BUNDLE.zip",
  "sha256": "a4d54c2d1b59730cc13f0e1c6835d9d59795f33f368f2287af9dedf8706903bc",
  "release_version": "4.3.0-human-validated-final"
}
```

```json
{
  "verified": true,
  "archive_count": 5
}
```

Both `unzip -t` commands completed with `No errors detected in compressed data`.

## Verified release facts

- Release identity: `MGP-6 v4.3.0-human-validated-final`.
- Master bundle SHA-256: `a4d54c2d1b59730cc13f0e1c6835d9d59795f33f368f2287af9dedf8706903bc`.
- Five internal archives: public train/dev, private hidden inputs, private hidden
  gold, private audit package, and source/builder.
- Readiness verdict: `READY_FOR_FINAL_PAPER_EXPERIMENTS`.
- Failed release gates: none.
- Release facts: 900 items, 100 components, and locked splits of
  180 train / 180 dev / 540 hidden items (20 / 20 / 60 components), with exact
  per-split class balance.

## Privacy handling during verification

Only archive filenames, manifests, and readiness metadata were inspected.
Private JSONL content, hidden labels, final human gold, private mappings, and
completed annotation records were not opened, printed, copied, or passed to a
model.

## Final pre-install integrity check

Immediately before release placement, the nested release ZIP passed `unzip -t`.
The supplied outer handoff ZIP had SHA-256
`08a24e3269883a3445309889796a0aec3bdd840410912f4e3b73008340e25c9a`.
The authoritative nested-bundle SHA remains the verified release value above;
the outer handoff checksum is recorded here only as a local transport audit.
