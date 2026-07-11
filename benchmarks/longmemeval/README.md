# LongMemEval integration

The repository does not redistribute LongMemEval conversations or the 950 MB recovered slice.

Place licensed/local copies in one of these ignored paths:

```text
data/external/longmemeval/longmemeval_s_cleaned.jsonl
data/external/longmemeval/longmemeval_m_cleaned.jsonl
```

Then run:

```bash
python scripts/build_slice.py --help
python scripts/run_baseline.py --help
```

Tests that require the private 50-item computation fixture skip automatically when it is absent.
