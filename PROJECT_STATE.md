# Project state

**Repository status:** Git-ready canonical source tree assembled on 2026-07-12.

## Completed

- Full KSA implementation, scripts, tests, configs, prompts, and schemas restored.
- MGP-6 v2 dataset, benchmark code, adapters, and annotations integrated.
- Repository pollution removed.
- Scorer canonicalization defect patched with regression tests.
- OpenRouter Qwen/Gemma configuration added without embedding credentials.
- CI and public repository files added.

## Validation target

- Offline test suite: **420 passed, 14 skipped**.
- MGP-6 v2 strict schema validation: **180 examples, 0 errors**.
- Package build: validated with a no-dependency wheel build.
- Repository structure/secret scan: passed.

## Open blockers

- Fresh hosted-model confirmation experiments require network access and a rotated API credential.
- LongMemEval data is external and must be supplied locally.
- Official venue and institutional thesis templates must be selected before submission builds.
