# M2-W5 Summary

The extraction package now has a strict Pydantic schema, a prompt-rendering
`Extractor`, a frozen prompt at `prompts/extraction_v_final.j2`, and an
alarm-only `CoverageMonitor`. The prompt is precision-biased, rejects
assistant/filler/synthetic-prefix content, and emits marker fields now for later
error analysis.

Final dev-30 result on local Ollama `llama3.2:3b`: 27 correct, 3
over-extracted, 0 under-extracted, 0 schema violations, 0 marker errors.
Over-extraction is exactly at the 10% stop ceiling because assistant "Noted"
turns leaked the previous user preference. Holdout-10 was 10/10 correct on the
synthetic assertion-only holdout.

The local dataset is not representative: the checked-in LongMemEval slice is
synthetic and homogeneous. W6 should be interpreted as a pipeline/archive
exercise until a real stratified slice replaces the synthetic artifact.
