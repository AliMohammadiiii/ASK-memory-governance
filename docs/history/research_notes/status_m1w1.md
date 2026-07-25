# M1-W1 Status — Advisor handoff

**Week:** Month 1 Week 1 — Data & Environment
**Tag (planned):** `v0.1.0-m1w1`
**Date:** 2026-04-25

## One-paragraph status

Week 1 finalized against the laptop dev model (`gemma4:e4b` via local Ollama). Repo audit complete (no schema discrepancies vs. proposal §I.5.1 / §I.5.5). LongMemEval-S streaming loader, dataclass model, and competency-stratified slicer landed and tested. LLM inference harness ships three backends (`HuggingFaceLLM`, `OllamaLLM` with `/api/chat` mode, deterministic `FakeLLM`); the structured-output wrapper enforces pydantic schemas with one repair retry. The end-to-end smoke pipeline (LongMemEval session → LLM → SQLite + JSON-Schema-validated `action_log`) runs cleanly: 0.27 s on FakeLLM, 28.5 s on `gemma4:e4b` for an 11-token one-sentence answer, and is exercised on three sessions by `scripts/finalize_m1w1.sh`. Environment is locked (`requirements-lock.txt` reproduces the 50-test suite in a fresh venv). The original §5.3 GPU acceptance threshold (≥ 25 tok/s on A100 80GB for Llama-3-8B) is documented as a separate, pending criterion that runs when the GPU queue clears; the laptop bench is the M1-W1 closeout evidence per the user's "finalize with this model" decision. On track for Baseline 1 (no-memory) in Week 2.

## Acceptance criteria checklist (M1-W1 §5)

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `pytest` green, no skips | ✓ **50 passed** |
| 2 | `smoke_e2e.py` runs in < 60 s, populates SQLite | ✓ **0.27 s (FakeLLM)** + **28.5 s (gemma4:e4b)** |
| 3a | Bench: laptop dev path with gemma4:e4b | ✓ recorded by `scripts/finalize_m1w1.sh` → `NOTES/inference_bench.md` |
| 3b | Bench: A100/Llama-3-8B ≥ 25 tok/s | DEFERRED — GPU queue (Risk #1, open) |
| 4 | 50-session slice byte-stable under seed=0 | ✓ verified by `test_slice_jsonl_is_byte_stable` (sha256 round-trips) |
| 5 | Tag `v0.1.0-m1w1`; lockfile reproduces in fresh venv | ✓ lockfile verified; tag pending finalize-run commit |

## What landed this week (file inventory)

**Notes / docs**
- `NOTES/gap_audit_m1w1.md` — repo audit + schema-vs-proposal mapping
- `NOTES/longmemeval_mapping.md` — competency → {Keep, Supersede, Abstain}
- `NOTES/inference_bench.md` — bench report (overwritten by the laptop run, then again by the GPU run)
- `NOTES/run_local_smoke.md` — laptop dev path via Ollama / gemma4:e4b
- `NOTES/env.md` — sandbox + acceptance environment record
- `NOTES/finalize_m1w1.md` — closeout report from `scripts/finalize_m1w1.sh`
- `NOTES/status_m1w1.md` — this file

**Code**
- `src/ask/data/__init__.py`, `src/ask/data/longmemeval.py` — loader + slicer
- `src/ask/inference/__init__.py`, `src/ask/inference/llm.py` — Protocol, HF, StructuredLLM
- `src/ask/inference/fake.py` — deterministic dev/test stub
- `src/ask/inference/ollama.py` — Ollama HTTP backend (`/api/chat` + `/api/generate`)
- `src/ask/inference/structured_pai.py` — optional pydantic-ai wrapper

**Configs / data**
- `configs/inference.yaml` — primary (Llama-3-8B / Qwen2.5-7B fallback)
- `configs/inference-local.yaml` — Ollama dev preset (gemma4:e4b)
- `data/longmemeval_s_synthetic.jsonl` — placeholder corpus (200 sessions)
- `data/slices/longmemeval_s_50_seed0.jsonl` — canonical dev slice
- `data/slices/README.md`

**Scripts**
- `scripts/build_slice.py`
- `scripts/bench_inference.py` (HF + Ollama modes)
- `scripts/smoke_e2e.py` (FakeLLM / Ollama / HF)
- `scripts/finalize_m1w1.sh` — single-command finalization runner

**Tests** (added)
- `tests/test_longmemeval.py` (11)
- `tests/test_llm.py` (11)
- `tests/test_ollama.py` (6 — `/api/chat` + `/api/generate` payloads)
- `tests/test_e2e_smoke.py` (2)

**Lockfile**
- `requirements-lock.txt` — reproduces the 50-test suite cleanly in a venv
- `pyproject.toml` — concrete pins on core deps; bounded ranges on ML stack

## Risks closed / opened this week

| # | Risk | Status |
|---|------|--------|
| 1 | GPU queue wait blocks bench | **Open** — only blocker for the §5.3 threshold; M1-W1 finalized on laptop bench in parallel. |
| 2 | Llama-3-8B license/gating | **Mitigated** — Qwen2.5-7B fallback wired; harness model-agnostic. Dev path uses gemma4:e4b. |
| 3 | LongMemEval competency mapping ambiguity | **Closed** — mapping note filed; ≤ 20% borderline cases. |
| 4 | `action_log` missing fields needed later | **Closed** — schema verified field-for-field against §I.5.5. |
| 5 | Nondeterministic inference | **Closed** — `temperature=0.0` + fixed seed; covered by `test_determinism_same_prompt_seed_temp_zero`. |
| 6 | flash-attn / bitsandbytes install failures | **Closed** — both are optional imports. |
| 7 | Chat-tuned model emits empty answer via `/api/generate` | **Closed** — `OllamaLLM(chat=True)` defaults to `/api/chat`; verified live with gemma4:e4b. |

## Out-of-scope items confirmed unstarted

Per task §7: no baseline (Weeks 2–4), no FAISS (Week 3), no controller scoring beyond the Month-0 skeleton, no extraction prompt design (Month 2), no MGP-6 scenarios (Month 3), no runs at n > 50 (Month 4). All M1-W1 §7 boundaries respected.

## Handoff to M1-W2 (Baseline 1)

Week 2 picks up with the no-memory baseline. The pieces it needs are now in place:

- `iter_longmemeval_s` over `data/slices/longmemeval_s_50_seed0.jsonl` for the 50-session iteration loop;
- `build_llm()` / `--ollama` / `--fake` for the inference call (gemma4:e4b on laptop, Llama-3-8B on GPU when available);
- `ActionLogWriter` for recording per-session decisions (Baseline 1 will record `action="Keep"` with a baseline-marker rationale);
- `scripts/smoke_e2e.py` shows the exact shape Baseline 1 will scale up.

Week 2 deliverable target: a no-memory baseline that runs over all 50 sessions, records per-session predicted-vs-gold, and posts an aggregate accuracy + latency note.
