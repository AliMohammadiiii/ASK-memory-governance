# Contributing

## Development workflow

1. Create a focused branch from `main`.
2. Run `bash scripts/setup_venv.sh` and activate `.venv`.
3. Keep runtime behavior in `src/ask` and add regression tests under `tests`.
4. Run `make check` while iterating and `make release-check` before review.
5. Record benchmark- or claim-affecting changes in `CHANGELOG.md`,
   `DECISION_LOG.md`, and the relevant machine-readable registry.

Follow the existing module and naming conventions. Avoid new runtime
dependencies unless the behavior cannot be implemented with the standard
library or an existing dependency; explain the scope and optionality in the
change.

## Repository boundaries

Do not commit:

- credentials, `.env` files, private conversations, or participant identities;
- external datasets whose license does not permit redistribution;
- model caches, local databases, run directories, compiled publications,
  preview renders, or handoff archives;
- copied canonical data or figures when a build step can assemble a standalone
  deliverable.

Historical evidence is not ordinary prose. Regenerate a dated report from its
machine-readable source instead of silently editing results or claim status.

## Pull-request checklist

- [ ] The change is scoped and documented.
- [ ] New behavior has tests.
- [ ] `make check` passes.
- [ ] `make release-check` passes when release, data, or packaging behavior
      changes.
- [ ] No secret, private input, generated output, or unsupported scientific
      claim entered the diff.
