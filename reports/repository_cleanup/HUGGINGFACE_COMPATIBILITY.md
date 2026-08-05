# Hugging Face compatibility validation

## Locked environments

The maintained Python 3.12 ML environment resolves from
`constraints/ml-py312.txt` with these relevant versions:

- Transformers 5.14.1
- Sentence Transformers 5.6.1
- PyTorch 2.13.0
- Accelerate 1.14.0
- PEFT 0.20.0
- Hugging Face Hub 1.26.0
- Tokenizers 0.22.2
- Safetensors 0.8.0

The external-baseline environment resolves independently from
`constraints/external-baselines-py312.txt`. It retains Transformers 4.57.6 for
MemoryOS 2.0.23 while using Sentence Transformers 5.6.1 and PyTorch 2.13.0.
`pip check` passed in both isolated environments. Historical results and their
recorded environment files were not modified.

## Immutable model revisions used for live checks

- `hf-internal-testing/tiny-random-gpt2` at
  `71034c5d8bde858ff824298bdedc65515b97d2b9`
- `sentence-transformers/all-MiniLM-L6-v2` at
  `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`

## Executed paths

The following paths executed successfully without paid providers or private
data:

- Direct `HuggingFaceLLM` loading and deterministic generation.
- Hugging Face judge construction, revision propagation, loading, and
  generation.
- Sentence Transformers loading at an immutable revision and two-row encoding;
  output was float32 with shape `(2, 384)` and unit row norms.
- Local embedding HTTP server on `127.0.0.1`; health and `/v1/embeddings`
  requests returned two 384-dimensional vectors.
- `scripts/run_baseline.py` on one synthetic session with a fake judge; one
  answer, prediction, judgment, JSON report, and Markdown report were produced.
- Serial and parallel M4 Hugging Face runner dry runs; both forwarded the exact
  LLM revision into the generated command.
- Mem0, Graphiti, Letta, and MemOS adapter imports in the isolated external
  environment.
- `scripts/run_external_lme.py --help` in the same external environment.

The hermetic compatibility target reported 68 passing tests and 2 opt-in live
embedding tests skipped. The live embedding execution above covers those
network and model-loading paths separately.

## Defects found and repaired

Two integration defects were exposed by live execution:

1. A missing Accelerate installation raised `ValueError`, which was incorrectly
   routed into the non-causal vision-model fallback. The fallback now runs only
   for an architecture-specific auto-class error; environment errors propagate
   directly.
2. `--answer-max-new-tokens` was not forwarded to the no-memory, flat-vector,
   and recency baselines. It is now forwarded to all three paths.

Transformers 5 receives the `dtype` loader argument. Transformers 4 receives
the legacy `torch_dtype` argument, preserving external-environment
compatibility. Answerer, judge, embedder, embedding server, serial runner, and
parallel runner all accept and propagate immutable revisions.
