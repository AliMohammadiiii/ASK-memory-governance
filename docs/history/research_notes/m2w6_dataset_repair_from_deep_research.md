# M2-W6 Dataset Repair From Deep Research

Date: 2026-05-21

Deep-research source archived at:

`../docs/research/2026-05-21_memory_relation_datasets_deep_research.md`

## Decision

The research report found no public dataset that natively releases the exact
unit needed here: one prior memory, one candidate memory, and one of
`support` / `contradict` / `supersede` / `unclear`.

The repaired dev set therefore uses the report's practical recommendation:

- DialogueNLI pair labels for `support`, `contradict`, and `unclear`.
- AlpsBench Task 2 public dev/validation gold updates for `supersede`.

The result is a derived candidate set and still needs manual audit before it is
treated as final thesis evidence.

## Files

- Canonical repaired set: `data/dev/relation_dev100_seed0.jsonl`
- Research-named copy: `data/dev/relation_dev100_research_seed0.jsonl`
- Metadata: `data/dev/relation_dev100_seed0.meta.json`
- Previous synthetic-controlled backup:
  `data/dev/relation_dev100_seed0.synthetic_controlled_backup.jsonl`
- Builder: `scripts/build_relation_dev100_from_research.py`

SHA-256:

`ee3b0567af825d6b94254a9c29a55336c6e0e9b98bce690dbab153202ebc74e6`

Previous synthetic-controlled backup SHA-256:

`1dc8ed12d0b22ccf1927d3eb85d1d3763aaa2674272edcb5d3684485c3a1612c`

## Label Distribution

| label | count | source |
|---|---:|---|
| support | 25 | DialogueNLI entailment |
| contradict | 25 | DialogueNLI contradiction |
| supersede | 25 | AlpsBench Task 2 `*_updated` memory ids |
| unclear | 25 | DialogueNLI neutral |

The builder filters AlpsBench rows to English-like text because the local
classifier runs use small Ollama models and the current prompt is English.

## Rebuild Command

```bash
source .venv/bin/activate
python scripts/build_relation_dev100_from_research.py \
  --seed 0 \
  --out data/dev/relation_dev100_research_seed0.jsonl \
  --meta-out data/dev/relation_dev100_research_seed0.meta.json
```

## Audit Checklist

- Candidate and prior are both atomic memory statements.
- Candidate and prior refer to the same user/person where required.
- Candidate and prior compare the same semantic slot.
- `supersede` rows contain durable update evidence, not just lexical conflict.
- `contradict` rows lack reliable temporal evidence for replacement.
- `unclear` rows are truly unrelated, under-specified, or unsafe to compare.
- Any DialogueNLI row that is not a plausible user memory should be replaced.

## Next Step

Rerun W7 and W8 on `data/dev/relation_dev100_seed0.jsonl`. The previous
all-support/synthetic result is no longer valid as a gate measurement.
