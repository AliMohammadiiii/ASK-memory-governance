# Prospective Annotation Protocol

Protocol version: `1.0-draft`  
Status: `HUMAN_PROTOCOL_APPROVAL_REQUIRED`  
Freeze rule: this protocol must be timestamped and approved before independent annotation begins.

## Objective

Annotators decide whether a candidate turn should preserve, replace, or withhold commitment to one prior standing state. They also identify attributable evidence and, for replacements, reconstruct the resulting value. They may exclude an item rather than force an invalid judgment.

## Independence and roles

Each valid item requires at least three independent annotators. Annotators must not have created provisional constructor labels, must not receive source mappings, and must not see other decisions before submitting their own. Annotator identifiers are private pseudonyms. Conflicts of interest are recorded privately.

An adjudicator must be different from every original annotator for the item. Adjudication is additive: original rows are immutable and referenced by exact canonical-row hashes. No annotation row is overwritten.

## Materials

The annotation bundle is allowlisted and contains only:

- protocol and manual versions;
- blind item JSONL;
- a blank annotation form;
- packet manifest and SHA-256 checksums; and
- synthetic training examples that are not evaluation items.

It excludes source IDs, user IDs, chat IDs, page IDs, revision IDs, private paths, split assignment, constructor action or rationale, source relation, resulting value answer, lineage answer, and all private mappings.

## Assignment

Item-to-annotator assignment is generated under a private random seed and must achieve at least three distinct annotators per retained item. Annotators work independently. A packet may be distributed only after explicit authorization and manual privacy review for that packet.

## Required response fields

Each row records:

- `blind_id`;
- `annotator_pseudonym`;
- `protocol_version`;
- either action or exclusion, but not both;
- confidence as an integer 1 through 5;
- evidence turn IDs;
- resulting value when required;
- nonempty rationale;
- exclusion reason when excluded; and
- optional ambiguity category.

For non-excluded rows, evidence must include the marked candidate turn. A protocol amendment is required for any exception.

## Decision order

1. Verify that the prior value is a single standing state.
2. Verify that the candidate addresses the same principal and slot.
3. Verify that the included context supports a chronological interpretation.
4. Decide whether the candidate clearly reaffirms or remains compatible (`KEEP`), clearly replaces (`SUPERSEDE`), or is unsafe to commit (`ABSTAIN`).
5. Exclude the item when any prerequisite fails.
6. Select all necessary evidence turns, including the candidate.
7. Enter the resulting value for `SUPERSEDE`; for `KEEP` and `ABSTAIN`, preserve the prior canonical value.
8. Record confidence and rationale.

## Immutability and audit

Submission creates a canonical JSON row and SHA-256 hash. After submission, corrections are new superseding administrative records; the original remains unchanged. The validation report checks uniqueness, coverage, semantics, evidence references, and absence of private metadata.

## Pilot continuation criteria

The following are prospective protocol candidates and require human approval before use as stopping rules:

- approximately 70 percent or more of mined candidates survive construction and annotation validity;
- nominal agreement around 0.60 or higher, unless a documented ambiguity analysis supports continuation;
- at least 90 percent of adjudicated `SUPERSEDE` items have reconstructable resulting states;
- all three actions receive meaningful support; and
- no critical unresolved privacy issue exists in a distributed packet.

These values are not automatically authorized and are not claims about current performance.

## Amendments

Any change after annotation begins must include an amendment identifier, date, rationale, affected items, whether hidden labels were inspected, and a plan for reannotation or sensitivity analysis. No silent instruction changes are permitted.

