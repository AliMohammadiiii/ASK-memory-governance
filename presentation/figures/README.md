# Defense figures

This directory contains reusable visuals accompanying the English and Persian
defense decks.

- Canonical architecture, evaluation-chain, and annotation-agreement sources
  live only under `docs/figures`. The release builder copies them into the
  standalone presentation package at build time.
- `main_results_{en,fa}.png`, `external_system_mapping_{en,fa}.png`, and
  `longmemeval_bounds_{en,fa}.png` are full-slide 1600×900 exports from the
  visually verified final decks. They retain the slide title, interpretation,
  source note, and scientific-status caveats.

The LongMemEval visuals deliberately report the homogeneous run as
`externally_pending`; they do not present the historical 77.2% failure replay
as a result.
