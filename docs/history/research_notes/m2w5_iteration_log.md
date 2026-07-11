# M2-W5 Extraction Iteration Log

Runtime convention: all recorded prompt probes used local Ollama, temperature
`0.0`, seed `0`. The final dev-30 run used `llama3.2:3b` because `gemma4:e4b`
returned empty completions on extraction-shaped prompts despite responding to
trivial JSON probes. No additional models were downloaded.

## V0

Prompt: `prompts/extraction_v0.j2`

Run command:

```bash
source .venv/bin/activate
python scripts/run_extraction.py --input data/dev/extraction_dev30_seed0.jsonl \
  --prompt prompts/extraction_v0.j2 --out runs/m2w5/v0/extractions.jsonl \
  --trace runs/m2w5/v0/trace.jsonl --ollama-model llama3.2:3b \
  --seed 0 --temperature 0.0 --max-new-tokens 192 --num-ctx 4096
```

Diff from nothing: baseline prompt with proposal typing text, precision rule,
negation/hedge guidance, JSON-Schema block, and ±1 window.

Motivating failure mode: the model copied the JSON-Schema instead of emitting
an extraction object. The run stopped on the first row after one repair retry.

Tally: `schema-violation=1/1`; no full dev-30 classification was meaningful.

## V1

Prompt: `prompts/extraction_v1.j2`

Run command:

```bash
source .venv/bin/activate
python scripts/run_extraction.py --input data/dev/extraction_dev30_seed0.jsonl \
  --prompt prompts/extraction_v1.j2 --out runs/m2w5/v1/extractions.jsonl \
  --trace runs/m2w5/v1/trace.jsonl --ollama-model llama3.2:3b \
  --seed 0 --temperature 0.0 --max-new-tokens 192 --num-ctx 4096 --limit 1
```

Diff from V0: added explicit no-content guidance and banned assistant
acknowledgements, greetings, filler, questions, and synthetic dataset prefixes.

Motivating failure mode: V0 over-attended to the schema block. V1 still copied
schema fragments on the one-row Ollama probe, so it remained unusable.

Tally: `schema-violation=1/1`.

## V2

Prompt: `prompts/extraction_v2.j2`

Run command:

```bash
source .venv/bin/activate
python scripts/run_extraction.py --input data/dev/extraction_dev30_seed0.jsonl \
  --prompt prompts/extraction_v2.j2 --out runs/m2w5/v2/extractions.jsonl \
  --trace runs/m2w5/v2/trace.jsonl --ollama-model llama3.2:3b \
  --seed 0 --temperature 0.0 --max-new-tokens 192 --num-ctx 4096 --limit 1
```

Diff from V1: added canonical text constraints and examples to reduce subject
drift and attribute invention.

Motivating failure mode: schema copying was partly resolved on the first row,
but evidence offsets remained weak and the full prompt still needed a more
forceful output skeleton.

Tally on one-row probe: `correct=1`, `schema-violation=0`.

## V3 / V Final

Prompt: `prompts/extraction_v_final.j2`

Run command:

```bash
source .venv/bin/activate
python scripts/run_extraction.py --input data/dev/extraction_dev30_seed0.jsonl \
  --prompt prompts/extraction_v_final.j2 \
  --out runs/m2w5/v_final/extractions.jsonl \
  --trace runs/m2w5/v_final/trace.jsonl --ollama-model llama3.2:3b \
  --seed 0 --temperature 0.0 --max-new-tokens 256 --num-ctx 4096
```

Diff from V2: marked the JSON-Schema as reference-only, moved a compact output
skeleton after the input, and added extractor-side recovery for the single
common consistency error where items are present but `no_extractable_content`
is missing or true.

Dev-30 tally:

| class | count |
|---|---:|
| correct | 27 |
| over-extracted | 3 |
| under-extracted | 0 |
| type-error | 0 |
| schema-violation | 0 |
| marker-error | 0 |

Stop-condition check:

- over-extraction: `3/30 = 10.0%` (passes at the ceiling)
- under-extraction: `0/30 = 0.0%`
- schema-violation: `0/30`

Qualitative summary: the final prompt handles synthetic user preference turns
reliably, but it leaks the previous user preference into three assistant
acknowledgement rows. That is exactly the stop-condition ceiling and should be
watched on a real non-synthetic dev pool.
