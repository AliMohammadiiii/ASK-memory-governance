# Native and mapped external-system evaluation

Four evidence classes must remain distinct:

1. **Vocabulary mapping** converts an observed native state change into an ASK
   label. It is not a native ASK decision.
2. **Conformance evaluation** checks which ASK invariants a backend can expose
   through a fixture. Unsupported invariants remain N/A.
3. **Native system execution** calls the version-pinned backend's real write and
   retrieval APIs and records its native state/telemetry.
4. **Native objective evaluation** scores the system on the objective it was
   designed to optimize, without forcing non-equivalent ASK semantics.

Existing Letta, Mem0, Graphiti, and MemOS runners under
`benchmarks/mgp6/external/` exercise native write paths but derive an ASK action
from observable state. NOOP cannot distinguish Keep from Abstain, and dual
active conflicts are not valid Supersede transitions. These are adapter-mapped
development diagnostics, not native rankings or superiority evidence.

No new native empirical execution was authorized in this pass. JMLR
cross-storage evidence remains blocked until exact backend versions, services,
licenses, controls, complete run artifacts, and contract-test results are
frozen and independently reviewed.
