# State and audit consistency

## Writes in one transaction

`ask.memory.operations.supersede` uses SQLite `BEGIN IMMEDIATE` to insert the
replacement record, link any supplied evidence, mark the prior record inactive,
and create the supersession relation. An exception before commit rolls back all
of those writes. A supersession retry against the same prior record after a
successful commit fails because that record is no longer active. The regression
tests `test_supersede_is_atomic_under_forced_exception`,
`test_supersede_retry_after_rollback_commits_exactly_one_transition`, and
`test_supersede_double_supersede_raises_loudly` pin these guarantees.

Retrieval uses active records only; history queries can still read inactive
records and follow the predecessor chain. The same SQLite transaction does not
include the JSONL action log.

## Separate audit file boundary

The pipeline commits its SQLite mutation before appending the action log row.
`ActionLogWriter` validates each row before writing and flushes/fsyncs on close,
but the database and JSONL file do not share a transaction. A process interruption
between those operations can leave a committed state change without its audit
row. The current code has no automatic cross-file reconciliation or exactly-once
retry mechanism. Mark such a run interrupted and reconcile from its durable
database and source inputs before continuing; do not blindly replay a controller
write against the already changed state.

Validation covers the atomic SQLite rollback and retry behavior above, active
retrieval/history behavior in `tests/test_memory_operations.py`, and JSONL
validation/append behavior in `tests/test_action_log.py`. The inter-file crash
window is documented as an operational boundary, not claimed to be atomic.
