# Release checklist

## Source release

- [ ] Confirm the intended package version matches `pyproject.toml`,
      `src/ask/__init__.py`, `CITATION.cff`, and `CHANGELOG.md`.
- [ ] Review `git status --short`; release from a clean worktree.
- [ ] Run `make release-check` on Python 3.11 or 3.12.
- [ ] Inspect `git diff --check` and the final staged diff.
- [ ] Verify the wheel contains `ask/resources/`, `ask/baselines/prompts/`, and
      `ask/py.typed`.
- [ ] Confirm no credentials, private conversations, participant identities,
      external datasets, local paths, caches, databases, or generated handoff
      bundles are included.
- [ ] Build the final handoff with
      `python scripts/release/build_final_release.py`; do not use
      `--allow-dirty` for publication.
- [ ] Verify generated manifests and archive checksums from an extracted copy.
- [ ] Add a real repository URL only after the public host exists.

## Scientific and academic handoff

- [x] License author-created MGP-6 material under CC BY 4.0.
- [ ] Obtain written consent before redistributing raw independent-human labels.
- [ ] Supply the external LongMemEval input and authorized hosted-model access
      before claiming a homogeneous final run.
- [ ] Complete the independent MGP-6 v3 confirmation protocol before making
      generalization claims.
- [ ] Select the official venue and University of Tehran templates.
- [ ] Fill administrative placeholders and review private application material
      outside the public repository.

Unchecked external items are release limitations, not permission to fabricate
data, credentials, consent, or institutional metadata.
