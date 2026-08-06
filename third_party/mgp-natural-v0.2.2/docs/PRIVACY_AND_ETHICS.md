# Privacy, Ethics, and Data Protection

## Threat model

MGP-Natural processes natural conversation and editorial history that can contain direct identifiers, quasi-identifiers, educational records, credentials, local paths, private repositories, precise time information, quoted third-party text, or deleted content. Cross-session and lineage links can increase re-identification risk even when direct identifiers are removed.

The main release threats are:

- direct disclosure through text or metadata;
- linkage through stable IDs, timestamps, artifact names, or rare phrasing;
- credential or secret leakage;
- educational or institutional disclosure;
- reconstruction of private user identity from cross-session continuity;
- exposure of deleted or sensitive Wikipedia content;
- label leakage through filenames, private fields, or packet order; and
- overclaiming anonymization or legal clearance.

## Layered controls

1. Source data remains private and git-ignored.
2. Automated pattern and entropy scans create hash-only public summaries.
3. Deterministic redaction creates a separate derivative and private change log.
4. Configurable NER support and manual review queues address contextual identifiers.
5. Cross-session mappings, source locators, and precise timestamps remain private.
6. HMAC blinding breaks released item ordering and source identity.
7. Nested prohibited-key scanning and an allowlisted ZIP protect annotation packets.
8. Manual privacy approval is a mandatory release gate.
9. Public packaging is fail-closed.

## Limits of automation

Regexes, entropy rules, and NER can miss identifiers, misclassify code, or destroy task meaning. A passed automated scan is not an anonymity guarantee and is never labeled privacy approval. Items whose safe redaction destroys the decision are excluded.

## Data minimization

Annotators receive only the principal type, scope, slot, prior value, necessary dialogue, candidate marker, and turn IDs. Source IDs, identity-bearing continuity, local paths, precise timestamps, course metadata, private mappings, and constructor fields are excluded.

## Cross-session state

Cross-session items create special linkage risk. They require stronger scientific evidence and stricter privacy review. Released packets do not expose a stable user key or enough unrelated chats to profile an individual.

## Editorial content

Public availability of Wikipedia history does not eliminate privacy obligations. Deleted, reverted, or sensitive text receives separate review. Attribution, ShareAlike, modification notices, and handling of contributor identity are legal-review questions rather than machine approvals.

## Intended use

The benchmark is intended for research on write-time state governance, uncertainty, evidence attribution, state reconstruction, and lineage. It is not intended for identity inference, surveillance, automated grading, disciplinary action, user profiling, or reconstructing deleted content.

## Human subjects and institutional review

The repository does not decide whether a specific use requires IRB, ethics-board, data-protection, or institutional approval. The release checklist requires a recorded human determination by the responsible institution before distribution or human annotation.

