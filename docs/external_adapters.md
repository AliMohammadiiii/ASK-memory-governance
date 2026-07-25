# External adapters

MGP-6 includes experimental adapters for Letta, Mem0, MemOS, and Graphiti under `benchmarks/mgp6/external`. They are optional and excluded from ordinary offline tests.

Every comparison must document:

- package/service version;
- enabled memory configuration;
- per-scenario state isolation;
- native behavior and ASK action mapping;
- whether snapshots are full active state or top-k retrieval;
- retries and failures;
- semantic limitations of the comparison.
