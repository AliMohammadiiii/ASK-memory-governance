from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_GOLD = ROOT / ".private/benchmarks/mgp6/v4.3/hidden_gold/hidden_gold.jsonl"
LME_JUDGMENTS = ROOT / "runs_local/lme_final_controller_v12_qwen_180/controller/judgments.jsonl"


requires_private_evidence = pytest.mark.skipif(
    not PRIVATE_GOLD.is_file() or not LME_JUDGMENTS.is_file(),
    reason="private/locally retained evidence is unavailable in the public checkout",
)


def _load(relative: str, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@requires_private_evidence
def test_claim_builder_recomputes_every_headline_claim() -> None:
    ledger = _load("scripts/claims/build_claim_ledger.py", "claim_builder").build_claims(
        "2026-08-02T00:00:00+00:00"
    )
    assert len(ledger["claims"]) >= 24
    assert {claim["status"] for claim in ledger["claims"]} == {"verified"}
    assert len({claim["claim_id"] for claim in ledger["claims"]}) == len(ledger["claims"])


def test_claim_ledger_matches_schema() -> None:
    ledger = json.loads((ROOT / "claims/claims.json").read_text())
    schema = json.loads((ROOT / "claims/claims.schema.json").read_text())
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(
        ledger
    )


def test_exact_mcnemar_fixture() -> None:
    builder = _load("scripts/claims/build_claim_ledger.py", "claim_builder_stats")
    assert builder.exact_mcnemar(31, 8) == 0.0002940768754342571


@requires_private_evidence
def test_claim_verifier_has_zero_unexplained_mismatch_after_build(tmp_path: Path) -> None:
    builder = _load("scripts/claims/build_claim_ledger.py", "claim_builder_write")
    ledger_path = tmp_path / "claims.json"
    builder.write_outputs(
        builder.build_claims("2026-08-02T00:00:00+00:00"),
        ledger_path,
        tmp_path / "claims.csv",
    )
    verifier = _load("scripts/claims/verify_claims.py", "claim_verifier")
    report = verifier.verify(ledger_path)
    assert report["status"] == "PASS"
    assert report["unexplained_mismatch_count"] == 0
