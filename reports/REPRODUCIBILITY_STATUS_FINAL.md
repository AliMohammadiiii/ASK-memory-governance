# Final Reproducibility Status

Date: 2026-08-06

## Verdict

**CONDITIONAL GO.** The maintained code, protocol tests, claim ledger, paper
tables, and manuscript build are reproducible offline. The sealed MGP-6 hidden
run and paid LongMemEval inference are preserved historical evidence and were
not rerun. Public redistribution, full V12 provenance finality, and MGP-Natural
gold construction remain incomplete.

## Environment

- Supported local interpreter: `.venv/bin/python`
- Repository command surface: `make help`
- Paper build: `scripts/validation/build_manuscripts.py`
- No paid API call was made during this audit.
- No hidden split was rescored for configuration selection.
- Historical manifests and raw results were not rewritten.

## Evidence lineage

### MGP-6 v4.3

- Version: `4.3.0-human-validated-final`
- Model: `qwen/qwen3.5-9b`
- Provider recorded by the frozen run: OpenRouter
- Seed: 4301
- Decoding: temperature 0, maximum 128 new tokens, reasoning effort `none`
- Prompt hash:
  `3ffa2ae8df004a4b04c03eaf17ca39d1a57060da718d4a42ec6f67e1a3158619`
- Frozen controls: `experiments/mgp6_v43/FINAL_HIDDEN_CONFIG.json`
- Raw run: `runs/mgp6_v43/final_hidden/`
- Derived metrics:
  `artifacts/analysis/mgp6_v43_full_benchmark_analysis.json`
- Valid/skipped: 540/0 hidden examples in the reported final artifact
- Statistical unit: semantic component for clustered intervals

The run is not repeated because the sealed hidden split has already been
consumed and the repository prohibits hidden-set reuse for selection.

### LongMemEval-M V12

- Slice: 180 questions, six competencies by 30, seed 0
- Slice hash:
  `f10b4fb4173d3e2d9310d90c2b6bf8f5e7b147cea1d04affa9037b1b9fe6787d`
- Answer model: `qwen/qwen3.5-9b`
- Judge: `google/gemma-4-31b-it`
- Raw artifacts:
  `runs_local/lme_final_controller_v12_qwen_180/{controller,b1,b2,b3,b4}/`
- Valid/skipped: 180/0 final question judgments per system
- Controller action log: 12,654/0 replayed decisions
- Derived metrics: `artifacts/analysis/lme_v12_scorecard_analysis.json`

The result is a final candidate, not a fully homogeneous frozen run. The
historical manifest remains nonterminal and the homogeneity report records one
stale launcher hash. The final adjudicated per-system reports and judgments are
the score source; the stale pre-adjudication aggregate is not.

### MGP-Natural

- v0.1.0 is a quarantined 36-item feasibility seed with no independent gold and
  no valid held-out continuity split.
- v0.2.2 is vendored construction software. Its safe intake audit embeds no
  source dialogue, source identifier, or annotation.
- StudyChat human-AI and WikiConv human-human construction counts are workflow
  receipts, not evaluated benchmark denominators.
- No MGP-Natural model score is reported or regenerated.

## Final validation commands

| Command | Outcome |
|---|---|
| `make paper PYTHON=.venv/bin/python` | PASS; 47-page PDF built |
| `make verify-paper-artifacts PYTHON=.venv/bin/python` | PASS; 5 files and 20 required fragments |
| `make verify-claims PYTHON=.venv/bin/python` | PASS; 26 claims, 0 mismatches |
| `make advisor-check PYTHON=.venv/bin/python` | PASS; repository, prompt, prose, path, Ruff, format, mypy, compile, shell, claim, and provenance checks; 686 passed, 14 optional skips |
| `make release-check PYTHON=.venv/bin/python` | PASS; complete offline release gate and package build |
| `make mgpn-natural-v022-test PYTHON=.venv/bin/python` | PASS; 132 tests, 1 expected duplicate-member warning in a tamper-rejection test |
| `make clean-reproduction PYTHON=.venv/bin/python` | PASS from commit `bcde14c`; fresh environment, 684 tests passed and 14 optional tests skipped |
| Named-manuscript identity scan | Expected non-anonymous result; the canonical source names Ali Mohammadi and a blind copy must be generated separately if required |
| Publication readiness | `NO_GO` with 15 open gates, including the now-unsatisfied anonymous-release gate |
| `git diff --check` | PASS before final validation |
| PDF render and 47-page visual inspection | PASS; no clipping or unreadable figure/table found |

## Reproduction boundaries

- Offline gates reproduce maintained code behavior and paper drift checks, not
  paid model outputs.
- Raw LongMemEval data and private natural-dialogue inputs are not public
  artifacts.
- MGP-6 v4.3 cannot be advertised as an unrestricted public dataset until a
  license is selected.
- Machine checks cannot substitute for MGP-Natural privacy, consent, rights,
  independent annotation, or adjudication decisions.
- The clean-reproduction receipt removes local paths and checkout identity from
  public command/output tails while retaining hashes and exit codes.
