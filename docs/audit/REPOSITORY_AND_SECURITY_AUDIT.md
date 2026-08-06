# Repository and security audit

Audit date: 2026-07-13. Scope: the Git tracked set plus unignored candidate release files in the working tree. Large ignored evidence directories and source archives were treated as private inputs, not public-release contents.

## Executive decision

No high-confidence credential or private-key material was found in the tracked
and unignored candidate set scanned. The OpenRouter credential supplied during
execution was not persisted. A sanitized public snapshot has now been built and
validated: it excludes historical workstation-path documents and both raw
independent-human annotation CSVs, while retaining aggregate statistics and
their hashes. The snapshot is technically ready for a public repository; the
real host metadata, raw-label consent if those files are ever added, and the
externally pending LongMemEval run remain separate user/external actions.

## Checks performed

| Check | Scope | Result |
|---|---|---|
| High-confidence secret scan | Tracked and unignored candidate files at the audit checkpoint | No OpenRouter-style secret, AWS access-key identifier, or PEM/OpenSSH private-key header found |
| Git history review | All commits currently present; one commit in this local history | No high-confidence credential found; shallow/single-commit history cannot attest to any upstream history not supplied |
| Secret-bearing filename review | Tracked files | Only .env.example is tracked; no .env, private key, credential file, SQLite database, or local vector store is tracked |
| Ignore-policy review | .gitignore | .env variants, keys, local databases, runs, runs_local, external data, raw/final artifacts, inputs_raw, audit_workspace, and final_release are excluded |
| Workstation-path scan | Sanitized public snapshot | Passed; `docs/history/` is excluded and the active thesis-readiness audit was sanitized |
| Host metadata review | pyproject.toml, CITATION.cff, Git configuration | No Git remote is configured; placeholder URLs have been removed and repository URLs are intentionally omitted until a real public host exists |
| Data-license review | LICENSE, LICENSE-DATA.md, benchmark contents, final public ZIP | Software/docs are MIT; author-created MGP-6 materials are declared CC BY 4.0; two raw independent-human CSVs are withheld pending consent; LongMemEval is not redistributed |
| Release packaging review | Explicit public allowlist/exclusions and extracted archive | Passed; aggregate reports/manifests retained, private applications and raw run artifacts excluded, fail-closed scan clean |

The string-pattern scan is a useful guard, not proof that arbitrary prose, binaries, archives, or encoded content contains no sensitive material. Source ZIP files were inventoried by hash but were not approved for direct publication.

## Findings

### 1. Supplied credential

The external credential was consumed only from process environment input and was not written to the repository. Minimal API requests returned HTTP 403 before inference. Public artifacts record only that non-secret outcome. The credential should be rotated or replaced and must not be reused.

Severity: high if reused; contained in the repository snapshot.

### 2. Public-host metadata not yet established

No Git remote is configured. Placeholder OWNER URLs were removed from pyproject.toml and CITATION.cff, so the local package does not advertise a false host. Repository and issue URLs remain intentionally absent until the user creates or identifies the public repository.

Required action: after the user creates or identifies the public repository, add the real host to both metadata surfaces, verify issue and source links, and regenerate package metadata. Do not invent a host or account name.

Severity: external-publication blocker, not a blocker for the local release candidate and not a secret.

### 3. Absolute workstation paths in historical documentation

Eight tracked files under the private historical archive retain a
user-specific home-directory prefix:

- docs/history/ARTIFACT_MANIFEST.md
- docs/history/research_notes/m3w11_provenance.md
- docs/history/research_notes/m4w13_50_t4_controller_partial_answer_analysis.md
- docs/history/research_notes/m4w13_modal_hf_b1_controller_status.md
- docs/history/research_notes/m4w13_runs.md
- docs/history/research_notes/m4w14_thesis_colab_20260608_review.md
- docs/history/research_notes/m4w15_runbook.md
- docs/history/research_notes/m4w16_runbook.md
The active `docs/evaluation/thesis_readiness_audit.md` was sanitized. The release builder
excludes all of `docs/history/` and fails if the active machine-home prefix is
found anywhere in the public snapshot.

Disposition: resolved for the public artifact; the private historical notes
remain local evidence and must not be copied into a public branch or release.

### 4. Raw annotation redistribution

The independent annotator's raw per-item labels are not covered by the author's CC BY declaration without documented permission from that contributor. LICENSE-DATA.md says the public release withholds the raw label and disagreement files, but both files are currently tracked:

- benchmarks/mgp6/annotations/human/human_independent_annotations_test.csv, 2,605 bytes; SHA-256 dbc649d7c846a9c8a187ffca34dd68e802ac9c0f9fcccd66994a789b121facd9
- benchmarks/mgp6/annotations/human/human_vs_author_disagreements.csv, 675 bytes; SHA-256 bb98a34e09ed3d9f6cda4bfe5be6f7cf2de85d4c1d9a31792d8e44e743602182

The final public directory and its nested ZIP exclude both files. They retain
only the aggregate report/summary and
`benchmarks/mgp6/annotations/human/withheld_sources.sha256.json`. If the current
local Git history is ever published instead of the sanitized snapshot, remove
the raw files from that history or first obtain and archive written consent. Do
not imply that withholding proves the files contain personal data; this is a
rights and consent constraint.

Disposition: resolved for the sanitized public artifact; consent remains a gate
only for adding the raw labels.

### 5. External datasets and raw model output

LongMemEval data is external and large; its redistribution rights were not established. Historical prompts, answers, judgments, traces, and logs can reproduce source conversations or provider response text and therefore require a separate privacy and license review.

Required action: ship only dataset hashes, the deterministic slice procedure, IDs where permitted, aggregate metrics, and code. Keep raw evidence in access-controlled storage. Run the packaging fail-closed scan before release.

Severity: high if raw directories or archives are published wholesale.

### 6. External evidence integrity

The supplied v7 and v8 evidence directories are live external folders. They are now bound by deterministic whole-tree SHA-256 values in artifacts/manifests/source_archives.json. Their associated ZIP hashes remain separate identities and do not establish byte equivalence with the live folders.

Required action: keep the source directories read-only and recompute the documented tree-hash method before accepting a relocated or restored copy. Keep the raw snapshot private unless separately approved.

Severity: controlled reproducibility risk.

### 7. Dependency and build assurance

Core runtime dependencies are constrained. After the final source edits, Ruff,
mypy, 424 offline tests, strict MGP-6 validation, sdist/wheel builds, and an
isolated wheel install/import/resource check passed. The outer archive and
nested public ZIP were integrity-tested and extracted; their checksums and the
per-file manifest bind the delivered bytes. An SBOM and live vulnerability-feed
scan were not generated and remain optional host-publication hardening.

Disposition: local release gate passed; a future public host may add its own
dependency-advisory workflow.

## Release allowlist

Suitable for public packaging after final validation:

- source code, schemas, prompts, tests, and configuration without credentials;
- author-created MGP-6 dataset and documentation under LICENSE-DATA.md;
- aggregate MGP-6 results classified final_candidate;
- explicitly labeled diagnostic, incomplete, and failure-replay audit summaries without raw conversations;
- frozen experiment protocol, model identifiers, hashes, and deterministic preparation scripts; and
- paper, thesis, proposal, and presentation artifacts after claim and path scans.

Exclude unless separately cleared:

- .env files, credentials, keys, private configuration, or provider billing/account metadata;
- LongMemEval JSONL or source conversations;
- raw answers, judgments, prompts, traces, and logs from historical runs;
- independent-human raw annotations without written redistribution consent;
- SQLite/vector databases and caches; and
- the supplied ZIP archives as wholesale release assets.

## Final security gate

Final local gate status:

1. real public-host URLs, **user action**; no host was fabricated;
2. workstation-specific paths in the public set, **pass**;
3. raw-annotation exclusion, **pass**; written consent is required only to add them;
4. explicit sanitized snapshot rather than recursive workspace copy, **pass**;
5. secret/path/excluded-file scan and ZIP integrity checks, **pass**;
6. per-file manifest, internal checksums, outer ZIP SHA-256, validation report, and license inventory, **pass**; and
7. clean-directory extraction, tests, strict schema check, build, and isolated install, **pass**.

The local sanitized artifact is complete. Creating the real remote and adding
host metadata are external publication steps; they do not alter the scientific
status of LongMemEval, which remains `externally_pending`.
