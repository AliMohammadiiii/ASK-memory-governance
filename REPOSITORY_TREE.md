# Repository tree

The repository is organized by ownership and lifecycle rather than by a flat
inventory of every file:

```text
ask-memory-governance/
├── src/ask/                 # maintained installable package
├── tests/                   # automated verification
├── benchmarks/              # diagnostic data, protocols, adapters, and fixtures
├── configs/                 # active and frozen configuration
├── prompts/                 # prompt sources
├── schema/                  # LinkML, SQL, and JSON schema sources
├── scripts/
│   ├── analysis/            # report generation and validity audits
│   ├── evaluation/          # frozen evaluation entry points
│   ├── release/             # manifest, audit, and package builders
│   ├── setup/               # platform-specific setup wrappers
│   └── smoke/               # offline smoke orchestration
├── deploy/                  # environment-specific execution wrappers
├── docs/
│   ├── audit/               # scientific source-of-truth and traceability
│   ├── figures/             # canonical reusable figures
│   ├── history/             # superseded and dated research snapshots
│   └── reproduction/        # focused reproduction guides
├── artifacts/               # committed evidence, ledgers, and manifests
├── claims/                  # machine-verifiable claims and source inventory
├── confirmation/            # blinded prospective confirmation scaffolding
├── reports/                 # dated human-readable analytical outputs
├── paper/                   # paper sources and publication strategy
├── publication/             # venue requirements and submission checklists
├── readiness/               # executable publication-gate definitions
├── release/                 # public/private, license, and provenance policy
├── thesis/                  # thesis sources and administrative placeholders
├── presentation/            # defense decks, notes, and deck-specific exports
└── .github/workflows/       # continuous integration
```

## Boundary rules

- Runtime code belongs in `src/ask`; reusable behavior should not be copied into
  experiment scripts.
- Generated runs, caches, local databases, compiled documents, preview renders,
  and handoff archives are ignored.
- Canonical reusable figures live in `docs/figures`; release builders may copy
  them into standalone deliverables.
- Historical notes stay under `docs/history` and do not define current commands.
- External or private data is referenced by contract and checksum, never
  redistributed by convenience.
- `advisor_handoff/` and `final_release/` are generated, ignored outputs. They
  are never authoritative source trees.

Use `git ls-files` for an exact versioned inventory. This document intentionally
stays concise so it does not become stale after every file addition.
