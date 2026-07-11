# M4-W14 Pipeline Audit & Fix (2026-05-29)

**Verdict: `runs/m4w14` and `runs/m4w15` are INVALID.** A P0 extraction bug
silently discarded valid extracted memories on 46/60 MGP-6 scenarios. The fix is
landed and verified by replaying the original model outputs; the benchmark must
be re-run before any thesis claim.

## 1. Root cause (confirmed)

Small extractors emitted a valid first-pass object that omitted the required
`no_extractable_content` flag, e.g.:

```json
{"items": [{"text": "I now prefer green tea in the morning instead of coffee.", "type_guess": "stable_pref", ...}]}
```

Path before the fix:

1. `ExtractionOutput` strictly required `no_extractable_content` → first-pass rejected.
2. `StructuredLLM.generate_json` issued its one repair retry.
3. The repair collapsed to `{"items": [], "no_extractable_content": true}`.
4. `generate_json` returned that empty object **as a success**, so the
   extractor's own `_recover_output` (which only runs when `generate_json`
   *raises*) never executed. The real item was lost.

Trace evidence (`runs/m4w14/controller/extraction_trace.jsonl`, scenario
MGP6-T1-01): `responses[0]` = the green-tea item; `n_responses = 2` (repair
fired); `validated_output` = empty.

Downstream effect: 46/60 scenarios produced no candidate, so recency,
naive-overwrite, and the controller all fell into their "no candidate" branch
and produced **byte-identical confusion matrices** (controller ≡ b4). SMRR was
also identical (22/65) — not because the controller matched overwrite, but
because neither system saw a candidate.

## 2. Fix (landed)

- `src/ksa/extraction/schema.py`: `mode="before"` validator infers
  `no_extractable_content` from `items` **only when the field is absent**. An
  explicitly inconsistent flag is still rejected (strict against malformed).
- `src/ksa/classifier/schema.py`: `mode="before"` validators default an omitted
  `rationale` while keeping the relation/temporal label, so an omitted rationale
  no longer collapses a real contradiction to `independent`/`unclear` → Keep.
- `src/ksa/inference/llm.py`: `generate_json` gains an optional `trace` dict
  recording `parse_path` / `repair_used` / `first_error` / `repair_error`.
  Because the before-validators make recoverable output valid on the first pass,
  the repair call is skipped entirely for that output, so a successful-but-empty
  repair can no longer overwrite a good first pass.
- `src/ksa/extraction/extractor.py`: trace now logs `parse_path`, `repair_used`,
  `first_parse_error`, `repair_parse_error`.

## 3. Verification without a live model

Replaying every original m4w14 first-pass response through the fixed parser
(`tests/test_extraction_repair_regression.py`):

| | scenarios with ≥1 extracted item |
|---|---:|
| m4w14 as shipped | 14 / 60 (23%) |
| fixed parser, same model outputs | 48 / 60 (80%) |

34 scenarios flip from empty → recovered. The remaining 12 are genuinely empty
first passes (legitimate).

## 4. New diagnostics

- **`superseded_recoverability`** (`ksa.eval.recoverability`,
  `scripts/evaluate_recoverability_mgp6.py`) — the H2 metric SMRR cannot
  provide. On the *invalid* m4w14 outputs it already separates the systems:
  controller = 1.0 (9/9 revisions recoverable), naive overwrite = 0.0 (0/9).
- **Run-level sanity checks** (`ksa.eval.sanity`, wired into `scripts/run_mgp6.py`)
  — flag low extraction recall (< 50%) and byte-identical confusion matrices
  among distinct-policy systems, writing `sanity_report.json` and (optionally,
  `--fail-on-sanity`) exiting non-zero. Run against m4w14 these fire exactly the
  warnings that would have caught this bug.

## 5. Audited adjacent issues

| Area | Finding | Action |
|---|---|---|
| Extraction schema | omitted `no_extractable_content` discarded items | fixed + regression tests |
| Classifier schema | omitted `rationale` collapsed label to fallback | fixed + tests |
| Repair behavior | empty repair silently overwrote good first pass | eliminated via before-validators; trace records repair path |
| Candidate generation | no per-run extraction-recall check | sanity check added |
| SMRR vs H2 | SMRR ties controller and overwrite | added `superseded_recoverability` |
| `_active_prior_for` / `_find_prior` | newest same-type prior only | documented limitation in code; top-k semantic prior is Part II |
| LongMemEval m4w13 | `raw_turn_fallback=true` + `same_as_answerer` judge + b1/controller only | flagged in manifest; final run must set fallback off, all systems, stable judge |

## 6. Required re-run (on a machine with Ollama models)

```bash
cd ksa_controller
source .venv/bin/activate

# 1. MGP-6 all-system re-run (final-candidate), with sanity gate ON.
python scripts/run_mgp6.py \
  --input data/mgp6_v1_seed0.jsonl \
  --systems all \
  --model-profile light \
  --seed 0 \
  --n-bootstrap 1000 \
  --scorecard-config configs/controller_active.yaml \
  --out runs/m4w14_rerun \
  --note-path NOTES/m4w14_mgp6_results.md \
  --fail-on-sanity

# 2. Lineage auditability (H2) and SMRR from the re-run.
python scripts/evaluate_recoverability_mgp6.py --run-root runs/m4w14_rerun
python scripts/evaluate_smrr_mgp6.py            --run-root runs/m4w14_rerun

# 3. RC@C (M4-W15) regenerated from the re-run controller action log, not m4w14.
```

Acceptance after re-run: `sanity_report.json` has `ok: true`; controller and b4
confusion matrices differ; extraction recall ≥ 0.5 on updating systems;
`superseded_recoverability` controller=1.0 / b4=0.0.

LongMemEval-S final candidate must additionally use `raw_turn_fallback=false`,
all five systems, and a stable (non same-as-answerer) judge.
