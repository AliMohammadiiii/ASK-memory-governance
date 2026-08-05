# Adjudication Protocol

Protocol version: `1.0-draft`  
Status: `HUMAN_PROTOCOL_APPROVAL_REQUIRED`

## Preconditions

Adjudication begins only after annotation validation confirms at least three distinct, immutable source rows for every item under review. The adjudicator must not be one of the source annotators and must not have created the provisional constructor judgment.

## Inputs

The adjudicator receives:

- the same blind item seen by annotators;
- all validated annotation rows with annotator pseudonyms optionally masked;
- exact canonical hashes of those rows;
- a structured disagreement summary; and
- the approved annotation and adjudication manuals.

The adjudicator does not receive private source mappings, constructor labels, split assignment, or hidden test status.

## Additive record

An adjudication row records:

- blind ID;
- adjudicator pseudonym;
- protocol version;
- exact ordered source-row hashes;
- exact multiset of source actions;
- exact exclusion count;
- final action or explicit exclusion;
- adjudicated evidence turn IDs;
- adjudicated resulting value;
- rationale; and
- optional ambiguity and amendment metadata.

Original annotation rows remain immutable. Any later change creates a new adjudication version and preserves the previous row.

## Resolution method

The adjudicator re-applies the task contract rather than automatically choosing a majority. Majority and confidence are evidence about disagreement, not authoritative gold. The adjudicator must explicitly resolve:

- whether the prior is atomic and standing;
- whether principal and slot match;
- whether chronology and context are adequate;
- the primary action;
- evidence sufficiency;
- the resulting value; and
- whether ambiguity requires exclusion.

A disputed item may be excluded. The protocol does not require retaining a target class.

## Validation

Machine validation verifies:

- at least three source annotations;
- distinct original annotators;
- separate adjudicator;
- exact source-row hashes;
- exact action multiset and exclusion count;
- one final action or exclusion;
- valid evidence IDs including the candidate for non-excluded rows;
- changed result for `SUPERSEDE`;
- preserved prior result for `KEEP` and `ABSTAIN`;
- nonempty rationale; and
- complete item coverage for any declared adjudicated set.

## Gold boundary

A validated adjudication is not yet public gold. Gold construction additionally requires manual privacy approval, authorized mapping reveal, split audit, legal and redistribution approval, and a recorded release decision. Gold rows are marked `annotation_status = independently_adjudicated_gold` only after all gates pass.

