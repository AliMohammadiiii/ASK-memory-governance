# Documentation map

This page defines the maintained documentation entry points and prevents dated
research snapshots from competing with current instructions.

## Start here

- `../README.md`, project scope, setup, repository map, and release entry point.
- `development/ADVISOR_START_HERE.md`, supervisor reading order and review commands.
- `architecture/ASK_PROTOCOL.md`, normative protocol, transition, and invariant contract.
- `architecture/ADAPTER_CONTRACT.md`, ASK-MGP/ASK-LME trace and replay boundaries.
- `architecture/REPOSITORY_ARCHITECTURE.md` - repository and protocol ownership.
- `architecture/SOURCE_OF_TRUTH.md` - authority for code, data, experiments,
  evidence, manuscripts, and generated outputs.
- `architecture/REPOSITORY_TREE.md` - concise maintained tree.
- `reproducibility/README.md` - evidence and clean-reproduction contract.
- `reproducibility/QUICKSTART.md` - public offline reproduction path.
- `reproducibility/ENVIRONMENT.md` - interpreter, dependency, and platform scope.
- `reproducibility/RESULT_PROVENANCE.md` - source-to-claim lineage.
- `reproducibility/GENERATED_FILES.md` - generated-output ownership and tracking policy.
- `evaluation/TMLR_READINESS.md` and `evaluation/JMLR_READINESS.md`,
  venue-specific blockers.
- `reproduce_results.md`, benchmark-specific reproduction commands and evidence
  boundaries.
- `evaluation/evaluation_protocol.md`, evaluation semantics and required disclosures.
- `evaluation/limitations.md`, canonical technical and scientific limitations.
- `troubleshooting.md`, common installation, external-data, and provider issues.
- `development/release_checklist.md`, source-release and academic-handoff checklist.

Compatibility pages such as `known_limitations.md` contain pointers only. New
links should target the canonical pages above.

## Scientific authority

When documents disagree, use this order:

1. machine-readable ledgers and manifests under `artifacts/`;
2. `audit/SCIENTIFIC_SOURCE_OF_TRUTH.md` and `audit/CLAIM_ELIGIBILITY.md`;
3. maintained protocols and limitation pages under `docs/`;
4. dated reports under `reports/`;
5. publication drafts under `paper/` and `thesis/`;
6. archived notes under `history/`.

Consumed evidence reports are unchanged unless their generating script and
machine-readable source are regenerated together. A newer maintenance pass does
not silently rewrite historical experimental claims.

## History and generated outputs

`history/` contains superseded runbooks, debugging notes, and research logs.
They may mention old dependency files, model IDs, commands, or test counts and
must not be treated as current setup instructions. Generated figures belong in
`docs/figures`; presentation-only exports belong in `presentation/figures`.
Build previews, caches, compiled documents, and release ZIPs remain untracked.
