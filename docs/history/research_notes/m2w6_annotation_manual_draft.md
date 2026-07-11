# M2-W6 Annotation Manual Draft

## Unit Of Annotation

Each row is one current turn with a fixed ±1 surrounding window. Labels are
assigned to the candidate memory represented by the row, not to the full
session.

## Type Label

- `stable_pref`: durable user preference, habit, standing dislike, or recurring
  default.
- `transient_pref`: short-lived preference, current plan, immediate constraint,
  mood, or one-off request.
- `episodic_fact`: concrete event, commitment, relationship, activity, or
  personal fact. Events and commitments are collapsed here by proposal scope.

If a row contains no candidate memory, no type label should be assigned. The
current synthetic dev-100 contains only stable preference assertions.

## Relation To Prior State

- `support`: compatible with and reinforces the prior memory state.
- `contradict`: logically conflicts with a prior memory but does not clearly
  replace it.
- `supersede`: newer statement should replace the prior state.
- `unclear`: relation cannot be determined from the turn and prior state.

For the current synthetic dev-100, the assumed prior state is the canonical
coffee preference, so every row is labelled `support`.

## Marker Correctness

Marker correctness is `Yes` when the extractor's `negation_marker`,
`hedge_marker`, and `polarity_subject` match the source turn. It is `No` when
any emitted marker is wrong, and `N/A` when no extractor item exists.

For the current synthetic source, expected markers are:

- `negation_marker=false`
- `hedge_marker=false`
- `polarity_subject="user"`

## Notes

The checked-in source is too homogeneous for a real G2 measurement set. Replace
this file's criteria with concrete examples once the real LongMemEval-S slice
is available.
