# Annotator Manual

Manual version: `1.0-draft`

## What you are deciding

You are reviewing one possible write to a stateful memory. The item gives a prior standing value and a later candidate turn. Decide what a careful system should do at write time.

## KEEP

Choose `KEEP` when the candidate clearly supports, repeats, reaffirms, or remains compatible with the prior value. The standing value stays exactly the same after canonicalization.

Typical evidence:

- explicit continuation language;
- a repeated preference with the same value;
- confirmation that an existing task or artifact choice remains active; or
- new information that does not conflict with the standing value and explicitly supports it.

Do not use `KEEP` merely because the candidate fails to prove a replacement. Uncertainty belongs under `ABSTAIN`.

## SUPERSEDE

Choose `SUPERSEDE` when the candidate clearly changes the same state slot. The new resulting value must be recoverable from the visible text and materially different from the prior value.

Typical evidence:

- explicit correction;
- “use X instead”;
- a replacement filename or method;
- a clear reversal of an interaction preference;
- an editorial modification, deletion, or restoration supported by source context; or
- a resolved decision that replaces an earlier standing decision.

Exclude rather than supersede when the new value cannot be determined.

## ABSTAIN

Choose `ABSTAIN` when the candidate is relevant to the slot but should not become standing state. The prior canonical state remains unchanged because commitment is withheld, not because it was affirmed.

Typical evidence:

- “maybe,” “perhaps,” or “not sure”;
- a hypothetical or conditional proposal;
- unresolved disagreement;
- referential ambiguity;
- evidence that conflicts without resolving which value stands; or
- a request to verify before changing state.

## EXCLUDE

Exclude when no valid one-slot MGP decision exists. Common reasons are:

- no prior standing state;
- unrelated slot or principal;
- a question or multi-value predecessor;
- a candidate containing multiple independent updates;
- missing context or unverifiable chronology;
- unresolved resulting value for a replacement;
- pure acknowledgment;
- assignment text rather than an active state;
- inaccessible external evidence;
- privacy redaction that makes the decision unintelligible; or
- multiple equally valid interpretations.

Never force an item into one of the three actions to avoid exclusion.

## Evidence selection

Select the minimum sufficient set of turn IDs that supports your judgment. The candidate turn is always required for a non-excluded row. Include predecessor evidence and any disambiguating context. Do not select every turn by default.

## Resulting value

For `SUPERSEDE`, enter the value that should stand after the candidate. Preserve meaningful spelling, filename, code token, wording, or deletion marker. Do not invent a value from hidden knowledge.

For `KEEP` and `ABSTAIN`, copy the prior standing value as the canonical resulting value. The interface may populate it automatically, but verify that it has not changed.

## Confidence

- `1`: a valid decision is barely possible; exclusion may be preferable.
- `2`: substantial ambiguity remains.
- `3`: more likely than alternatives but not decisive.
- `4`: clear with minor interpretive uncertainty.
- `5`: explicit and unambiguous from the released evidence.

Confidence does not replace exclusion. Exclude items that fail the task contract.

## Track-specific cautions

For StudyChat, do not turn transient implementation details into identity attributes. A preference is cross-session only when the item explicitly supplies cross-session evidence under the protocol.

For WikiConv, distinguish proposal, support, opposition, consensus, implementation, rollback, and unresolved dispute. A talk-page proposal is not page state unless visible evidence supports implementation.

## Privacy and reporting

Do not search for the source conversation, identify users, or retain item text outside the authorized environment. Report any possible identity, secret, grade, submission, deleted sensitive content, or unsafe quotation through the private escalation channel. Do not copy the sensitive string into ordinary notes.

