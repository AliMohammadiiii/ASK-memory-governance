# MGP-Natural v0.1.0 Engineering Finalization Record

Date: 2026-08-03

## Verdict

MGP-Natural v0.1.0 is a `QUARANTINED_RELEASE_CANDIDATE`.

It is an internally coherent, 36-item Wikipedia editorial-discussion feasibility seed with provisional constructor labels. It is not independently annotated gold, not a valid held-out benchmark, not cleared for public redistribution, and not eligible for leaderboard or paper-result use.

The repository integration preserves this boundary. The supplied ZIP remains an external evidence input. No raw MGP-Natural records, source mappings, constructor labels, private annotation artifacts, or release-paper copies were imported into the authoritative source tree.

The recorded `PASS_PRIVATE_DRAFT_VERIFICATION` result applies only to the structure, leakage guards, commitments, and reproducibility of a private draft packet. It does not authorize annotation, unsealing, publication, or redistribution.

## Pinned inputs

SHA-256 identifies the exact reviewed inputs.

| Input | Role | SHA-256 |
|---|---|---|
| `MGP-Natural-v0.1.0-release.zip` | Candidate archive and only source of dataset audit facts | `0ffe92eba00bcec503e81589965c381857f4524fdd955902678d636eca7b7f26` |
| Final-delivery assessment attachment | Supporting review, not an executable source of truth | `f49082f37f2fb4f7e920c585b84efcb42a2ee4945f4f3e9e50a642dce5cb4a90` |
| Audited-neighbor and real-chat-source attachment | Supporting search report, not a benchmark artifact | `6459f07ed717624b0fbcf581ce78bf944e89353f37538ac5a60dfde84345c50d` |

The archive auditor rejects a ZIP whose hash differs from the pinned archive hash. Claims in the two prose attachments are not promoted automatically into the paper, claim ledger, or release metadata.

The generated path-neutral derived manifest is
`artifacts/manifests/mgp_natural_v0_1_1_derived_audit.json`, with SHA-256
`1a0579fb8ed1e7a01d5cb570c4a13849a319b59caf9309f36ff437ef0fd4d8fd`.
It records repository evidence hashes and aggregate anomalies without embedding
external text, item labels, source identifiers, private material, or local
paths.

## Exact archive audit findings

The machine-readable audit is `confirmation/natural_challenge/mgp_natural_v0_1_0/archive_audit.json`.

### Seed composition

| Finding | Audited value |
|---|---:|
| Records | 36 |
| Unique record IDs | 36 |
| Normalized dialogue excerpt rows | 76 |
| `KEEP` provisional labels | 12 |
| `SUPERSEDE` provisional labels | 12 |
| `ABSTAIN` provisional labels | 12 |
| Declared train, dev, test rows | 24, 6, 6 |
| Rows marked `expert_provisional_seed` | 36 |
| Rows requiring independent confirmation | 36 |
| Rows with completed independent adjudication | 0 |
| Multi-contributor excerpts | 31 |
| Single-contributor excerpts | 5 |

The count 76 means normalized excerpt rows in the package. It does not establish 76 independent source comments or 76 independent conversational turns. The count 36 means distinct packaged records, not statistically independent discussions.

### Archive integrity

- ZIP integrity passed.
- The manifest contains 136 entries.
- Manifest missing, extra, duplicate, and hash-mismatch counts are all zero.
- The declared split files reconstruct the canonical seed file exactly.
- Record IDs are unique.

These checks establish internal package consistency. They do not independently verify every excerpt against its upstream Wikipedia revision, reproduce the original source selection, or establish legal redistribution approval.

### Split and continuity audit

- Exact test page-title overlap with train or dev is 0.
- Test page-family overlap with train or dev is 1.
- Test contributor overlap with train or dev is 1.
- A continuity graph that connects records sharing a normalized page family or contributor has 2 components, sized 35 and 1.
- One continuity component crosses declared splits.
- The current split is therefore not an independent continuity-held-out split.

The defensible description is "exact page-title holdout." Claims of page-family holdout, contributor holdout, zero split leakage, or independent held-out evaluation are not supported.

### Original packet label leakage

The file presented as a blind packet inside the supplied archive is unsafe.

- `relation_to_prior` is present in 36 of 36 packet rows.
- The packet exposes source IDs that join directly to 36 of 36 seed labels.
- The deterministic rule `supports -> KEEP`, `supersedes -> SUPERSEDE`, and all other relations `-> ABSTAIN` recovers 36 of 36 provisional actions.
- The original packet must never be sent to independent annotators.

This is a complete label shortcut for this seed, not a minor metadata concern.

### Release state

- The archive release checklist has 32 unchecked items.
- Required sign-offs are incomplete.
- Human, legal, and privacy approval is pending.
- The confirmation protocol remains `NOT_EXECUTED`.
- `preregistered_before_labels` is false.
- `human_legal_approval` is false.
- Paid inference is not authorized.

## What was integrated

The integration is deliberately limited to audit and future-confirmation infrastructure:

- A pinned, read-only archive auditor and aggregate audit report.
- A path-neutral derived-manifest builder that pins all three reviewed inputs, records aggregate anomalies, and hashes the relevant code, schemas, and protocol without embedding external payloads.
- A label-free projection for a new private packet.
- Shared nested-key leakage guards and an allowlisted packet builder.
- HMAC-SHA256 blinding with a private reveal record and public commitments.
- A verifier that reproduces a private packet from the pinned parent and private reveal record.
- Natural-challenge, annotation, and adjudication schema support for `N######` identifiers.
- Semantic annotation and adjudication validators.
- A guarded scorer for future independently adjudicated gold.
- Offline Make targets for audit, dry-run tests, private packet creation, and private verification.
- An intentionally failing public-package target.
- Aggregate verification artifacts under `confirmation/natural_challenge/mgp_natural_v0_1_0/`.
- Release-boundary entries that keep the parent ZIP, derived private packet, future annotations, and external real-chat corpora out of the public artifact until their specific gates pass.
- Unit tests for relation leakage, source identity removal, annotation semantics, adjudication binding, and provisional-score refusal.
- Unit tests for deterministic derived-manifest generation, pinned-input refusal, atomic output, and exclusion of paths and private payloads.

## What was deliberately excluded

The following material was not merged:

- The raw 36-item seed, declared split files, source excerpts, and source locators.
- The archive's unsafe blind packet.
- Constructor labels, rationales, resulting states, lineage, and source-to-blind mappings.
- Private packet files, the blinding secret, answer forms, annotations, adjudications, gold, predictions, and score outputs. These belong only below `.private/`.
- The supplied ASK paper copy, companion paper, generated PDFs, build logs, copied figures, copied tables, and final-report renderings.
- Hand-written release, authorship, license, novelty, benchmark, or publication claims.
- Candidate external datasets such as SWE-chat or StudyChat. Their access, consent, licensing, and transformation paths require separate review.
- Paid model calls, new model selection, hidden-split rescoring, and leaderboard runs.

## Derived private packet guarantees

The committed verification artifact is `confirmation/natural_challenge/mgp_natural_v0_1_0/private_packet_verification.json`. It records:

- Status `PASS_PRIVATE_DRAFT_VERIFICATION`.
- 36 packet items.
- 0 packet schema errors.
- 0 packet semantic invariant errors.
- 0 prohibited keys at any nesting depth.
- Exact reproduction from the pinned archive and saved private reveal record.
- A verified commitment to the private mapping.
- Verified hashes for the packet, protocol, schemas, and blinding transforms.
- A five-member ZIP allowlist with four payload entries covered by `SHA256SUMS`.
- ZIP integrity success.
- Absence of the private mapping from the annotation bundle.
- `annotation_authorized: false` and `publication_eligible: false`.

The projection removes labels, constructor relations, source IDs, source locators, contributor metadata, split metadata, post-decision state, lineage, and other prohibited fields. It redacts known contributor identity tokens plus detected email addresses, IPv4 addresses, URLs, and common secret-token patterns. It assigns `N######` IDs after keyed HMAC ordering. The default build creates a fresh 256-bit secret. A supplied secret must contain at least 128 bits. Private outputs are restricted to `.private/` and written without group or world permissions.

Exact packet reproduction requires the private reveal record because a fresh build intentionally generates a fresh random secret. The verifier can reproduce and bind an existing packet without publishing that secret or mapping.

These controls do not guarantee that heuristic redaction catches every possible identifier, that the source text is redistribution-cleared, or that annotators are independent. Human privacy review, legal approval, protocol freeze, and operational separation remain required.

## Annotation and adjudication rules

The future annotation path applies these rules:

1. Every annotation references a known blind ID and a nonempty annotator pseudonym.
2. A `(blind_id, annotator_pseudonym)` pair must be unique.
3. Every packet item requires at least three distinct annotators.
4. A row is either a labeled row or an exclusion row. A labeled row requires action, confidence, and rationale. An exclusion row uses `exclude_reason` and cannot also carry those label fields.
5. Actions are limited to `KEEP`, `SUPERSEDE`, and `ABSTAIN`. Confidence is an integer from 1 through 5.
6. Every nonexcluded labeled row requires evidence turn IDs. All evidence IDs must occur in the packet dialogue, and the candidate turn must be included.
7. `KEEP` and `ABSTAIN` must preserve the predecessor standing value.
8. `SUPERSEDE` requires a nonempty resulting value that differs from the predecessor standing value.
9. Adjudication is additive. Original annotation rows must remain immutable.
10. An adjudication needs at least three original annotations from distinct annotators, a separate adjudicator, the exact canonical hashes of the original rows, the exact multiset of original actions, and the exact original exclusion count. It resolves each item to either an action or an explicit exclusion and must cover every annotated blind ID.

Before a gold release, engineering review must also confirm complete adjudication coverage, exclusions, trajectory or cluster handling, and immutable storage. The current archive audit retains `SCORER_AND_VALIDATOR_HARDENING_REQUIRED` as a blocker.

## Scoring rules

The scorer is fail-closed by default:

- It refuses provisional or undocumented gold unless `--allow-provisional-smoke` is explicitly supplied.
- Final gold requires every gold row to have `annotation_status: independently_adjudicated_gold`.
- Gold and prediction IDs must be unique and must have exact coverage.
- Actions outside `KEEP`, `SUPERSEDE`, and `ABSTAIN` are rejected.
- Action outputs include accuracy, macro-F1, per-class precision, recall, F1 and support, plus a full confusion matrix.
- Optional resulting-state and lineage predictions use canonical whole-object exact match and report coverage.
- Optional evidence predictions use set F1 and report coverage.
- Input gold, predictions, and scorer script are SHA-256 recorded in the result.
- A provisional smoke score is never publication eligible.
- Publication and leaderboard eligibility require independently adjudicated gold, an audited valid held-out split, and at least three independent continuity components.
- Confidence intervals are not currently reported.

The present candidate fails the held-out and component gates. Its continuity audit has only two components, sized 35 and 1. The CLI split-validity flag and component count must eventually be supplied from a reviewed machine artifact, not asserted manually. No score from the current provisional labels is a paper result.

## Reproducible offline commands

Run these commands from the repository root with Python 3.11 or 3.12. Keep the pinned ZIP outside the tracked source tree and pass a relative path.

```bash
export MGP_NATURAL_ARCHIVE=../evidence/MGP-Natural-v0.1.0-release.zip
export MGP_NATURAL_DELIVERY_REPORT=../evidence/delivery-report.txt
export MGP_NATURAL_RESEARCH_REPORT=../evidence/research-report.txt

shasum -a 256 "$MGP_NATURAL_ARCHIVE"
shasum -a 256 "$MGP_NATURAL_DELIVERY_REPORT" "$MGP_NATURAL_RESEARCH_REPORT"
make mgpn-natural-audit PYTHON=.venv/bin/python
make mgpn-natural-manifest PYTHON=.venv/bin/python
make mgpn-natural-dry-run PYTHON=.venv/bin/python
make mgpn-natural-build-private PYTHON=.venv/bin/python
make mgpn-natural-verify-private PYTHON=.venv/bin/python
```

The build writes only private annotation materials below `.private/mgp_natural/v0.1.0/`, plus the aggregate audit report. The verification command writes only the aggregate private verification result to the tracked confirmation directory.

After annotation is authorized and collected, validate private JSONL artifacts with:

```bash
PYTHONPATH=src .venv/bin/python scripts/confirmation/validate_mgpn_annotations.py \
  --packet .private/mgp_natural/v0.1.0/blind_packet.jsonl \
  --annotations .private/mgp_natural/v0.1.0/annotations.jsonl \
  --adjudications .private/mgp_natural/v0.1.0/adjudications.jsonl \
  --minimum-annotators 3 \
  --output .private/mgp_natural/v0.1.0/annotation_validation.json
```

Do not construct or score gold until approved unsealing and adjudication are complete. The future scoring command is:

```bash
PYTHONPATH=src .venv/bin/python scripts/confirmation/score_mgpn_predictions.py \
  --gold .private/mgp_natural/v0.1.0/adjudicated_gold.jsonl \
  --predictions .private/mgp_natural/v0.1.0/predictions.jsonl \
  --output .private/mgp_natural/v0.1.0/score.json
```

The current public packaging gate must fail:

```bash
make mgpn-natural-package-public
```

Expected result: `BLOCKED_PENDING_HUMAN_LEGAL_PRIVACY_APPROVAL_AND_INDEPENDENT_GOLD`.

## Gates before annotation or release

All of the following gates remain open:

1. Freeze the task contract, hypotheses, primary and secondary endpoints, exclusions, unit of analysis, sample size, model versions, controller versions, and analysis plan before inspecting independent labels.
2. Obtain explicit human, legal, privacy, consent, attribution, and redistribution approval for the exact source material and intended packet.
3. Reproduce and audit the source-extraction ledger, including source revision, comment boundaries, selection rules, and text fidelity.
4. Run a manual privacy review of every derived packet item after automated redaction.
5. Redesign or expand the data so test records are isolated by page family and contributor continuity. Produce at least three independent continuity components before any publication-eligible score.
6. Recruit at least three annotators per item who did not construct the provisional labels, tune the system, or inspect the parent archive or private mapping.
7. Freeze individual annotation rows before adjudication. Use a separate adjudicator and preserve the committed row hashes.
8. Obtain one-time human authorization before revealing the source mapping. Do not unseal early.
9. Complete validator and scorer hardening, including full coverage checks, audited split inputs, cluster-aware uncertainty, and confidence intervals where the analysis requires them.
10. Regenerate the claim ledger, paper tables, release inventory, checksums, and GO or NO-GO report from machine evidence.
11. Complete every release-checklist item and record accountable human sign-offs before any public package, license declaration, DOI, or benchmark announcement.

## Next human actions

1. Assign an accountable data steward and legal or privacy reviewer.
2. Decide whether Wikipedia excerpts may be redistributed in the intended annotation and publication form, including attribution and share-alike obligations.
3. Approve or reject the normalized predecessor-state construction as a valid annotation task. It is not a native assistant-memory log.
4. Approve a page-family and contributor-aware sampling plan that breaks the current 35-item continuity component.
5. Freeze and sign the prospective protocol before recruiting annotators.
6. Select three or more independent annotators per item and a separate adjudicator. Record conflicts of interest and access restrictions outside the repository.
7. Authorize private packet distribution only after manual privacy review.
8. Authorize mapping reveal only after original annotations are immutable.
9. Review the final validation report, exclusion accounting, agreement analysis, adjudication record, and split audit.
10. Make a new explicit release decision. Until that decision, status remains quarantined.

## Allowed claims now

The following claims are supported if their qualifiers are retained:

- "MGP-Natural v0.1.0 is an internally coherent 36-item Wikipedia editorial-discussion feasibility seed with provisional constructor labels."
- "The seed contains 76 normalized excerpt rows and a balanced provisional action distribution of 12 `KEEP`, 12 `SUPERSEDE`, and 12 `ABSTAIN`."
- "Its declared split contains 24 train, 6 dev, and 6 test records, but it is not continuity-held-out."
- "Thirty-one excerpts contain multiple contributors and five contain one contributor."
- "The pinned ZIP and its 136-entry manifest passed internal integrity checks."
- "The original archive packet leaks the provisional label on 36 of 36 items and is unsafe for independent annotation."
- "A derived private draft packet passed structural, commitment, prohibited-key, and reproduction checks, but annotation and publication remain unauthorized."
- "The supplied neighbor review reported no exact task match among the sources it examined." This is a scoped report of that search, not a universal novelty or priority claim.

## Prohibited claims now

Do not claim any of the following:

- Independently annotated gold benchmark.
- Public-release-cleared or redistribution-cleared dataset.
- Valid page-family-held-out, contributor-held-out, or leakage-free test set.
- Leaderboard-quality, publication-ready, validated, representative, or externally generalizable benchmark.
- Representative real-world personal-assistant memory interactions.
- Thirty-six independent conversations or discussions.
- Seventy-six independent, native, or source-verified conversation turns.
- Complete source-to-release reproducibility or independently verified verbatim extraction.
- Independent adjudication, legal approval, privacy approval, preregistration, or completed release sign-off.
- Model performance, system superiority, safety, certification, or downstream improvement based on provisional smoke scoring.
- First, only, state of the art, universal, or exhaustive novelty.
- A finalized paper, public release, product-ready dataset, or successful external reproduction.

These restrictions remain in force until new direct evidence closes the corresponding gates and the machine claim ledger is regenerated without mismatches.
