# Repository architecture

ASK is an installable Python package and a research compendium. Directory
ownership follows lifecycle and authority, not file format.

## Executable system

`src/ask/` is the only package source. It separates candidate extraction,
relation classification, policy decisions, protocol traces, state transitions,
inference adapters, baselines, and evaluation. Reusable behavior belongs here.
Scripts may parse command-line arguments and coordinate runs, but new shared
logic must not be copied between scripts.

ASK separates five responsibilities:

1. Candidate formation produces a typed candidate and evidence references.
2. A policy proposes KEEP, SUPERSEDE, or ABSTAIN.
3. An adapter maps observations into the ASK trace and declares replay scope.
4. The transition engine applies deterministic state changes and retains
   predecessor links.
5. The audit layer validates configuration identity, evidence identity, action
   invariants, lineage, and replay equivalence.

`src/ask/protocol/` is the normative executable core. The extraction,
classifier, controller, memory, pipeline, baseline, and evaluation packages are
implementations around that contract.

```text
user event -> typed candidate -> evidence and relation analysis -> policy
proposal -> ASK trace -> KEEP | SUPERSEDE | ABSTAIN -> validated transition
-> provenance-constrained retrieval -> answer and evaluation
```

## Research system

`benchmarks/` owns benchmark definitions, validators, public inputs, scoring,
and adapter contracts. A benchmark label must never enter model-facing code.
Private labels, mappings, and non-redistributable inputs remain outside Git.

`configs/` contains maintained defaults and prospective run definitions.
`experiments/` records configurations and authorizations associated with
consumed or registered experiments. `prompts/registry.yaml` identifies every
prompt, its status, hash, and experiment relations. Reported configurations and
prompts are preserved by content hash even if a newer active default exists.

`artifacts/` contains committed machine-readable evidence, analyses, and
manifests. `reports/` contains human-readable outputs derived from that evidence.
Generated reports must identify their command or source. A report never outranks
the raw prediction, judgment, action log, or manifest that produced it.

## Manuscripts and release material

`paper/` and `thesis/` are separate document projects. They share verified
evidence through scripts, tables, and claim checks. They do not establish facts
by copying numbers from narrative reports. Compiled PDFs and editable exports
are local build outputs unless a release manifest explicitly lists them.

`release/` defines data, license, privacy, and public/private policy.
`scripts/release/` builds review and release packages. Expanded packages,
archives, local runs, private data, caches, and build products are ignored and
never become source trees.

## Historical records

`docs/history/` contains superseded notes and files retained to explain prior
decisions. A historical record may use old paths or commands. Current setup and
scientific claims must link to maintained documentation instead.

## Boundaries

- Runtime code: `src/ask/`
- Verification: `tests/` and validation scripts
- Benchmark contracts: `benchmarks/`
- Active configuration: `configs/`
- Experiment records: `experiments/`
- Prompt authority: `prompts/registry.yaml` and the referenced prompt files
- Machine evidence: `artifacts/`, `claims/`, and registered local evidence
- Human reports: `reports/`
- Current documentation: `docs/` outside `docs/history/`
- Paper and thesis: `paper/` and `thesis/`
- Public/private policy: `release/`
- Generated local output: ignored paths named in `.gitignore`

The detailed authority order is in `SOURCE_OF_TRUTH.md`. The maintained tree is
in `REPOSITORY_TREE.md`.
