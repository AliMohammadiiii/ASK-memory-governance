# Baseline Interfaces

The repository freezes interfaces for:

- no-memory: never proposes a state write;
- recency: uses the most recent relevant surface form;
- overwrite: replaces whenever a candidate value is extracted;
- flat retrieval: retrieves nearest prior turns without structured state;
- deterministic rule: applies explicit update, reaffirmation, and uncertainty patterns;
- zero-shot language model: external adapter requiring authorization;
- structured MGP controller: returns action, evidence, result, and lineage;
- oracle-evidence diagnostic: receives gold evidence but predicts action and state; and
- oracle-action reconstruction diagnostic: receives gold action but predicts resulting state.

All adapters emit one prediction schema and a run manifest. Paid APIs and silent fallback are disabled. Offline mock fixtures exercise every interface.

