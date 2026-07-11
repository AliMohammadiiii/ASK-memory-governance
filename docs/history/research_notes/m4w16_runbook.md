# M4-W16 Sanity Checks and G3 Runbook

Status update 2026-07-07: tooling is implemented, but the M4-W16 acceptance
artifacts have not been generated in this workspace. The valid MGP-6/RC@C
inputs are `runs/m4w14_thesis_colab_20260608/` and
`runs/m4w15_thesis_colab_20260608/`; the historical `runs/m4w14/` and
`runs/m4w15/` paths are invalid pre-fix evidence.

Prerequisite commands, using real Ollama outputs:

```bash
source .venv/bin/activate
python scripts/run_m4w13_ollama.py --model-profile light --slice /Users/ali/Downloads/longmemeval/longmemeval_s_cleaned.json
python scripts/run_mgp6.py --model-profile light --systems all --out runs/m4w14
python scripts/run_m4w15.py --model-profile light --longmemeval-slice /Users/ali/Downloads/longmemeval/longmemeval_s_cleaned.json
```

Check whether M4-W16 can run:

```bash
source .venv/bin/activate
python scripts/check_m4w16.py --check-only
```

Generate the M4-W16 deliverables:

```bash
source .venv/bin/activate
python scripts/check_m4w16.py --run-logreg-on-fail
```

Expected outputs:

- `NOTES/m4w16_qualitative.md`
- `NOTES/m4w16_threshold_validation.md`
- `NOTES/G3_gate_decision.md`
- `runs/m4w16/error_taxonomy.csv`
- `runs/m4w16/pattern_audit.json`
- `runs/m4w16/logreg_comparator.json` only if G3 fails and the comparator is requested

The checker fails closed when the real run artifacts are missing. It does not
create synthetic qualitative walkthroughs or placeholder error taxonomies.
