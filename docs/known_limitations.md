# Known limitations

- MGP-6 v2 is a 180-item diagnostic slice, not a comprehensive benchmark.
- Some templates and scorecard evidence may share lexical structure; confirmation data must avoid template leakage.
- LongMemEval transfer requires external data and is not part of the default offline suite.
- External adapters do not expose identical action semantics; mapping assumptions must be reported.
- Fresh Qwen/Gemma hosted-model results remain pending.
- The current repository preserves extensive legacy research scripts; the stable public API is `src/ask`, while old run wrappers remain documented but may require environment-specific setup.
