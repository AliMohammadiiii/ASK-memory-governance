# Data licensing notice

The repository's MIT license applies to software and documentation. It does not
automatically license third-party data, model outputs, or independent annotation
work.

## MGP-6 v2

The author-created MGP-6 v2 scenarios, schemas, gold labels, and benchmark
documentation are Copyright 2026 Ali Mohammadi and are released under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
(CC BY 4.0). Cite this repository and the accompanying paper/thesis when using
them. MGP-6 is a synthetic diagnostic, not a representative population sample or
an established community benchmark.

The independent human annotator's raw per-item labels are not covered by that
grant. The public release omits
`benchmarks/mgp6/annotations/human/human_independent_annotations_test.csv` and
`human_vs_author_disagreements.csv` until written redistribution consent is
recorded. Aggregate, non-identifying agreement statistics are retained for audit,
with hashes of the withheld source files. This is a licensing restriction, not a
claim that the raw labels contain personal data.

Model-audit outputs are provided as research artifacts without any warranty that
an upstream model provider grants broader rights in generated rationales. Users
must check the applicable provider terms before redistributing or republishing
those rationales.

## External data and outputs

- LongMemEval data is not redistributed. Obtain it from its upstream source and
  follow its license/terms; this repository stores only hashes and preparation
  instructions.
- Historical outputs from external systems are not part of the public release
  unless expressly listed in its manifest. Their upstream software/data terms
  remain applicable.
