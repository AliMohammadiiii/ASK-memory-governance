# M2-W5 Design Note

## Schema Decisions

The extractor emits `ExtractionOutput` with zero or more `ExtractedItem` rows.
Each item carries `text`, `type_guess`, an `EvidenceSpan`, raw
`extraction_confidence`, `negation_marker`, `hedge_marker`, and
`polarity_subject`.

The marker fields are included now even though the controller does not consume
them yet. They are cheap for the LLM to report, useful in Month-4 error
analysis, and avoid a Month-3 schema migration if negation/hedging becomes
load-bearing.

## Prompt Shape

The frozen prompt is `prompts/extraction_v_final.j2`. It keeps the proposal
§I.5.2 memory typing text, gives operational examples, repeats the
precision-over-recall instruction, rejects assistant acknowledgements and
synthetic dataset prefixes, and includes a JSON-Schema reference plus a compact
output skeleton.

The output skeleton was necessary for local Ollama behavior. `gemma4:e4b`
returned empty extraction completions for the full prompt. `llama3.2:3b`
returned usable JSON but sometimes omitted or inverted `no_extractable_content`;
the extractor therefore performs a narrow recovery only for that boolean
consistency issue and still returns the strict Pydantic schema.

## Coverage Monitor

`CoverageMonitor` is alarm-only in Month 2. It records recent items-per-turn and
alarms when the rate drops below `baseline_rate * alarm_factor`. It does not
relax the prompt. Without W6 labels, automatic relaxation would be an
uncontrolled precision loss.

Frozen dev-30 baseline rate:

- total items extracted: 30
- turns processed: 30
- `baseline_rate = 1.0`

This rate is inflated by the local synthetic slice, where almost every row is
the same coffee preference sentence. The value is still persisted as the local
reference for testing the monitor.

## Data Limitation

The checked-in LongMemEval artifacts are synthetic. The 50-session slice has
only one user turn per session, all with "I prefer coffee in the morning", plus
assistant acknowledgement turns. True W5 stratification across all memory types,
polarity, and length is impossible from this local artifact. The dev files carry
`local_source_limitation` metadata so this constraint is visible downstream.
