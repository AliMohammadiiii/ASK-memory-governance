# WikiConv / Wikipedia Talk Track

## Role in MGP-Natural

WikiConv is a natural human-human collaborative editorial-state and lineage track. The state-bearing entity is normally a page, section, claim, wording decision, source decision, or editorial issue. The track must not be interpreted as personal-assistant memory.

## Primary source evidence

The source audit prioritizes the official Conversation AI repository, the WikiConv paper, and official ConvoKit documentation. The official repository describes a corpus built from the July 1, 2018 Wikipedia history dumps and distinguishes the dataset wrapper license from the underlying individual comment text terms. The exact evidence, access date, and unresolved legal questions are recorded in `reports/WIKICONV_SOURCE_AUDIT.md` and `reports/WIKICONV_LICENSE_EVIDENCE.md`.

## Acquisition status

This execution records the official acquisition path but does not materialize natural WikiConv bytes. A bounded official natural reconstruction test-data path was identified, but the code runtime could not resolve GitHub, raw GitHub, or ConvoKit hosts. Browser-rendered responses were not substituted for source files and no manual transcription was performed. `scripts/acquire_wikiconv.py` supports resumable HTTP downloads, expected size and SHA-256 verification, source metadata capture, and fail-closed source-change behavior. Synthetic fixtures exercise the interface without being represented as natural corpus evidence.

The exact attempt and DNS evidence are recorded in `reports/WIKICONV_ACQUISITION_ATTEMPT.json`. A network-enabled, authorized rerun must hash and audit the exact source bytes before natural reconstruction.

## Source reconstruction

Where source history supports the fields, reconstruction preserves:

- action type: creation, addition, modification, deletion, restoration;
- reply and parent relations;
- conversation, thread, and section membership;
- normalized page family;
- contributor identity under private provenance;
- revision identifier and order;
- ancestor lineage; and
- deletion-restoration chains.

Broken parentage, ambiguous chronology, or action values that cannot be reconstructed are reported and excluded.

## State layers

The constructor keeps discussion state, committed page state, and revision action distinct.

- A proposal may change discussion state but does not establish a page write.
- Support or opposition may change consensus or dispute state but does not by itself implement content.
- A revision action may establish page state but not consensus.
- A rollback can restore prior page state while reopening or preserving a dispute.
- A deletion may be a committed state transition even if its motivating discussion is unresolved.

## Candidate scopes

Eligible scopes include editorial decisions, content inclusion or removal, wording, source status, consensus, dispute, revision, deletion-restoration, and editorial uncertainty. The scope controls interpretation and evaluation slices.

## Provenance and privacy

Private source locators support audit against page, revision, action, contributor, parent, and thread. Blind packets exclude all such identifiers. Deleted or sensitive content receives enhanced review; source availability is not treated as publication permission. The public release boundary can choose transformed excerpts, identifiers-only provenance, or no redistribution, subject to recorded legal and privacy decisions.

## Licensing boundary

The repository does not conclude that a wrapper license clears underlying comments, deleted content, contributor attribution, ShareAlike obligations, or modification notices. These are separate human legal-review questions. Public packaging remains blocked until the decision matrix records a human approval for the exact release form.

## Scientific interpretation

WikiConv permits evaluation of editorial-state transitions and lineage under natural collaboration. Its discourse structure, authority relations, and page/revision coupling differ substantially from StudyChat. Transfer results must be reported separately and interpreted in light of these domain differences.

