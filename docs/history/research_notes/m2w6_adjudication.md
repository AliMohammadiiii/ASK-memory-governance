# M2-W6 Adjudication Notes

## Dataset

File: `data/dev/relation_dev100_seed0.jsonl`

The 100 rows are disjoint from W5 dev-30 by `turn_id`. Because the checked-in
50-session slice has only 50 user turns, the W6 set is drawn from
`data/longmemeval_s_synthetic.jsonl` rather than only
`data/slices/longmemeval_s_50_seed0.jsonl`.

## Stratification

The local artifact does not support the requested type/polarity/length
stratification. All 100 rows are:

- `type=stable_pref`
- `relation_to_prior_state=support`
- assertion polarity
- one-line user turns

Every row carries `local_source_limitation` metadata.

## Extractor Marker Check

Frozen extractor run:

```bash
source .venv/bin/activate
python scripts/run_extraction.py --input data/dev/relation_dev100_seed0.jsonl \
  --prompt prompts/extraction_v_final.j2 \
  --out runs/m2w6/extractor_outputs.jsonl --trace runs/m2w6/trace.jsonl \
  --ollama-model phi3.5:3.8b --seed 0 --temperature 0.0 \
  --max-new-tokens 256 --num-ctx 4096
```

Result:

- 100/100 rows emitted one item.
- `marker_correctness=Yes` for 100/100 rows.
- Extractor model recorded in outputs: `phi3.5:3.8b`.

## Self-Adjudication

A true 24-hour cold re-label cannot be honestly completed inside this same
execution session. Immediate spot-check on the deterministic 20-row subsample
`lme-s-00000:0` through `lme-s-00021:0` had 20/20 agreement with the archived
labels, but this should be repeated cold before using the file as G2 evidence.

Raw immediate agreement: 100%.

## SHA-256

`relation_dev100_seed0.jsonl`:

`5b3e643244bc235d86bbe012570828dbb0e583e46a8b20242b75e25d3f32f27f`
