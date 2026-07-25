# Repo gap audit — M1-W1

**Date:** 2026-04-25  **Tag at start of week:** v0.1.0-m0 (post Scope_Reduction_Memo)
**Auditor:** Ali Mohammadi (`ali.mohammadi@cytognosis.org`)

## 1. What's already built (Month 0 close-out)

| Area | Path | Status |
|------|------|--------|
| LinkML schema source | `schema/ask_memory.yaml` | ✓ Complete; matches proposal §I.5.1 / §I.5.5 |
| Generated SQL DDL | `schema/generated/schema.sql` | ✓ Tables: `memory_items`, `evidence_spans`, `memory_evidence`, `memory_relations`, `action_log` |
| Generated JSON Schema | `schema/generated/ask_memory.schema.json` | ✓ Top class = `ActionLogEntry` |
| Memory dataclasses | `src/ask/memory/models.py` | ✓ `MemoryItem`, `EvidenceSpan`, `MemoryRelation`, `ActionLogEntry` + enums |
| DB connect/init | `src/ask/memory/db.py` | ✓ `connect()`, `init_schema()`, FK pragma on |
| Memory ops | `src/ask/memory/operations.py` | ✓ `insert_active`, `supersede` (atomic), `retrieve_active` |
| Controller features | `src/ask/controller/features.py` | ✓ Signatures stable; `explicitness`, `repetition`, `recency_protection`, `FeatureVector` |
| Controller scoring | `src/ask/controller/scoring.py` | ✓ `s_rev`, `s_abs`, `load_config`, named YAML config |
| Controller actions | `src/ask/controller/actions.py` | ✓ `decide()` with Abstain-wins-tie precedence |
| Action-log writer | `src/ask/audit/action_log.py` | ✓ JSONL + jsonschema validation |
| Default config | `configs/default.yaml` | ✓ Per-type weights + thresholds (proposal §I.5.5 Table) |
| Tests (skeleton) | `tests/` | ✓ 20 passing on Python 3.10 + Python 3.11+: `test_schema`, `test_supersede`, `test_scoring`, `test_actions`, `test_action_log` |

Result of `PYTHONPATH=src python3 -m pytest -q`:
```
....................                                                     [100%]
20 passed in 0.13s
```

## 2. Schema vs. proposal §I.5.1 / §I.5.5 — field-by-field

### `memory_items` (proposal §I.5.1)
| Proposal field | Schema column | Match |
|----------------|---------------|-------|
| `id`                  | `id INTEGER PRIMARY KEY`                  | ✓ |
| `type`                | `type TEXT CHECK IN (3 enums)`            | ✓ |
| `text`                | `text TEXT NOT NULL`                      | ✓ |
| `normalized_value`    | `normalized_value TEXT`                   | ✓ |
| `status`              | `status TEXT CHECK IN ('active','superseded')` | ✓ |
| `confidence`          | `confidence REAL CHECK ∈ [0,1]`           | ✓ |
| `created_at`          | `created_at TEXT` (ISO-8601 UTC default)  | ✓ |
| `valid_from`          | `valid_from TEXT`                         | ✓ |
| `supersedes_id`       | `supersedes_id INTEGER REFERENCES memory_items(id)` | ✓ |
| `evidence_span_ids`   | (normalized via `memory_evidence` bridge) | ✓ — represented as M:N table; dataclass exposes `evidence_span_ids: list[int]` |

### `action_log` (proposal §I.5.5)
| Proposal field | Schema column | Match |
|----------------|---------------|-------|
| `action` ∈ {Keep, Supersede, Abstain} | `action TEXT CHECK IN (3 enums)` | ✓ |
| `feature_snapshot` (c, e, f, r, ρ)   | `feature_c, feature_e, feature_f, feature_r, feature_rho` (each REAL ∈ [0,1] or NULL) | ✓ — *unfolded into named columns rather than a JSON blob; better for SQL aggregation. No semantic loss.* |
| `scores` (S_rev, S_abs)               | `s_rev REAL`, `s_abs REAL`               | ✓ |
| `rationale` (string)                  | `rationale TEXT NOT NULL`                 | ✓ |
| `timestamp`                           | `timestamp TEXT` (ISO-8601 UTC default)   | ✓ |
| (proposal-implicit) thresholds applied | `theta_sup REAL`, `theta_abs REAL`        | ✓ — present, useful for sensitivity analysis in M5 |
| (proposal-implicit) candidate text    | `candidate_text TEXT NOT NULL`            | ✓ |
| (proposal-implicit) prior memory ref  | `prior_memory_id INTEGER → memory_items`  | ✓ |
| (proposal-implicit) resulting memory ref | `resulting_memory_id INTEGER → memory_items` | ✓ |

**No discrepancies open.** All §I.5.5 fields are present and constrained. Notable upgrades over the bare proposal: `theta_sup` and `theta_abs` are recorded per-decision (lets us re-derive sensitivity curves in M5 without re-running the controller); `candidate_text` is required (lets us reconstruct decisions even if the source dialogue is rotated out).

### `evidence_spans` and `memory_relations`
Both present; columns match. `memory_relations.relation` is restricted to `{supports, contradicts, supersedes}` per §I.5.1 (no "unclear" stored — that is a classifier output, not a stored relation).

## 3. Gaps Week 1 closes

These are the items in M1-W1 §3 that did **not** exist in the Month-0 skeleton and will be added this week:

1. **No data ingestion.** Nothing in `src/ask/data/` yet. → §3.1 of the M1-W1 task adds `src/ask/data/longmemeval.py`, the slicer, and the `data/slices/longmemeval_s_50_seed0.jsonl` artifact.
2. **No inference harness.** Nothing in `src/ask/inference/` yet. → §3.2 adds `src/ask/inference/llm.py` (Protocol, `HuggingFaceLLM`, `StructuredLLM`).
3. **No end-to-end smoke.** No script that actually pulls a session through model → DB. → §3.3 adds `scripts/smoke_e2e.py` and `tests/test_e2e_smoke.py`.
4. **No environment lock.** `pyproject.toml` declares loose `>=` constraints; no `requirements-lock.txt`. → §3.4 freezes versions and tags `v0.1.0-m1w1`.
5. **No competency-to-action mapping** for LongMemEval-S. → §3.1 produces `NOTES/longmemeval_mapping.md`.

## 4. Gaps **not** closed this week (deferred to later weeks per §7 Out-of-scope)

- Baselines (no-memory, flat-vector, recency-pruning) — Weeks 2–4.
- FAISS / retrieval index — Week 3.
- Extraction prompt design — Month 2.
- Two-stage relation classifier — Month 2.
- MGP-6 scenario writing — Month 3.
- Running the slicer at `n > 50` — Month 4.

## 5. Risk register update (effective end of audit)

| # | Risk | Status after audit |
|---|------|--------------------|
| 1 | GPU queue wait | Unchanged — open |
| 2 | Llama-3-8B license/gating | Open; Qwen2.5-7B available as drop-in fallback per §3.2 |
| 3 | LongMemEval-S competency↔action mapping ambiguity | To be resolved by mapping note (§3.1) — drafted alongside this audit |
| 4 | `action_log` schema missing fields needed later | **Closed.** Schema verified field-for-field above; thresholds, candidate text, and both memory FKs are present. |
| 5 | Nondeterministic inference | Open — addressed in §3.2 with `temperature=0.0` + fixed seed test |
| 6 | `bitsandbytes` / flash-attn install failures | Open — handled by making them optional imports in §3.2 |

## 6. One-line summary

The Month-0 skeleton is sound; the schema does **not** need amending for §I.5.5 conformance. Week 1 work is purely additive: data loader, inference harness, smoke script, lockfile.
