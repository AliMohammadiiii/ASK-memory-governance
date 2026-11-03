# Formal core and executable claims

These are propositions under explicit implementation assumptions, not claims of
semantic truth or deployment safety.

## Endpoint non-identifiability

Assumption: an endpoint evaluator observes only the final answer string. Two
pipelines can emit the same string while one records Abstain with unchanged
state and another commits Supersede with altered lineage. Therefore endpoint QA
alone does not identify the write action, state integrity, or failed layer.
`tests/test_ask_formal_properties.py` constructs this counterexample.

## Replay sufficiency

Given stable identifiers, preserved adapter inputs, exact configuration
identity, ordered deterministic rules, evidence identity, the candidate/prior
records, and deterministic transition semantics, the final action and event are
deterministic. This does not regenerate the stochastic upstream model call.
ASK-MGP therefore claims composition-and-transition replay; ASK-LME claims
final-policy-and-transition replay.

## Preservation invariants

The executable validator enforces no commit on Abstain, preservation of the
compared prior on Keep, retained and resolvable predecessor on Supersede,
unique identifiers, acyclic and non-dangling lineage, and active uniqueness in
single-slot mode. Minimal counterexamples are in
`artifacts/formal/minimal_failure_traces.json`.

The propositions cease to apply if a trace omits required inputs, configuration
changes, identifiers are remapped, evidence is mutable, the transition has
side-effects outside modeled state, or the adapter overstates its replay scope.
