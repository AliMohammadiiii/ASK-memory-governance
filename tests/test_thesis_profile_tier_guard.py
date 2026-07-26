"""Locks the model-profile / tier-stamping guardrails.

These tests fail loudly if anyone reintroduces the runs/m4w14 mislabel, where a
3B `light` run was auto-stamped `final-candidate`. They enforce that:
  * a `thesis` profile exists and maps to a 7-8B extractor/classifier,
  * the sanity report exposes overall + T1 extraction recall and the spec floors,
  * the promotion gate refuses any run whose profile is not `thesis`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from ask.eval import sanity

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass annotation resolution can find the module.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_thesis_profile_is_7_8b_and_is_spec_profile() -> None:
    run_mgp6 = _load_script("run_mgp6")
    assert run_mgp6.SPEC_PROFILE == "thesis"
    extractor = run_mgp6.THESIS_MODELS["extractor"]
    # must not be a small dev model
    assert "3b" not in extractor.lower() and "3.8b" not in extractor.lower()
    assert any(tok in extractor.lower() for tok in ("8b", "7b"))


def test_sanity_exposes_spec_floors_and_t1_recall() -> None:
    assert sanity.SPEC_MIN_EXTRACTION_RECALL >= 0.9
    assert sanity.SPEC_MIN_T1_RECALL >= 0.9

    # synthetic report: 10 T1 scenarios, 6 with candidates -> T1 recall 0.6
    preds = []
    for i in range(1, 11):
        preds.append(
            {
                "scenario_id": f"MGP6-T1-{i:02d}",
                "candidate_type": "stable_pref" if i <= 6 else None,
                "predicted_action": "ABSTAIN",
            }
        )
    report = {
        "baseline": "controller",
        "predictions": preds,
        "confusion_matrix": {"ABSTAIN": {"ABSTAIN": 10}},
    }
    san = sanity.build_sanity_report([("controller", report)])
    ps = san["per_system"]["controller"]
    assert abs(ps["t1_extraction_recall"] - 0.6) < 1e-9
    assert san["thresholds"]["spec_min_t1_recall"] == sanity.SPEC_MIN_T1_RECALL


def test_promote_refuses_non_thesis_profile(tmp_path: Path) -> None:
    promote = _load_script("promote_to_final")
    run_root = tmp_path / "run"
    (run_root / "controller").mkdir(parents=True)
    (run_root / "b4").mkdir(parents=True)
    # a LIGHT-profile run that is otherwise complete must never promote
    (run_root / "manifest.json").write_text(
        json.dumps(
            {
                "model_profile": "light",
                "complete": True,
                "sanity_ok": True,
                "input": "data/mgp6_v1_seed0.jsonl",
            }
        )
    )
    (run_root / "sanity_report.json").write_text(json.dumps({"ok": True, "per_system": {}}))
    for alias in ("controller", "b4"):
        (run_root / alias / "predictions.jsonl").write_text("")

    import sys

    argv = sys.argv
    sys.argv = [
        "promote_to_final.py",
        "--run-root",
        str(run_root),
        "--mgp6",
        str(_SCRIPTS.parent / "data" / "mgp6_v1_seed0.jsonl"),
        "--check-only",
    ]
    try:
        rc = promote.main()
    finally:
        sys.argv = argv
    assert rc == 1
    assert not (run_root / "FINAL_OK.json").exists()


# --------------------------------------------------------------------------
# LongMemEval-S / RQ2 propagation: same thesis-profile / tier / promotion
# discipline as MGP-6.
# --------------------------------------------------------------------------


def test_lme_runner_thesis_profile_is_8b() -> None:
    runner = _load_script("run_m4w13_ollama")
    assert runner.SPEC_PROFILE == "thesis"
    roles = runner.THESIS_MODEL_ROLES
    for role in (roles.answerer, roles.extractor, roles.recency_extractor, roles.classifier):
        assert "3b" not in role.lower() and "3.8b" not in role.lower(), role
        assert any(tok in role.lower() for tok in ("8b", "7b")), role


def _make_lme_run(
    tmp_path: Path,
    *,
    profile="thesis",
    complete=True,
    synthetic=False,
    judge="gpt-4o",
    n_sessions=50,
    drop_system=None,
    clean_summary=True,
):
    """Build a synthetic LongMemEval run dir for gate testing."""
    run = tmp_path / "lme_run"
    run.mkdir(exist_ok=True)
    slice_path = tmp_path / "slice.jsonl"
    slice_path.write_text('{"question_id": "q1"}\n', encoding="utf-8")
    slice_sha = hashlib.sha256(slice_path.read_bytes()).hexdigest()
    systems = ["b1", "b2", "b3", "b4", "controller"]
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "model_profile": profile,
                "complete": complete,
                "slice": str(slice_path),
                "slice_is_synthetic": synthetic,
                "systems": systems,
                "judge_model": judge,
            }
        )
    )
    (run / "summary.json").write_text(
        json.dumps(
            {
                "missing_systems": [] if clean_summary else ["controller"],
                "validation_errors": [] if clean_summary else ["row count mismatch"],
            }
        )
    )
    for alias in systems:
        if alias == drop_system:
            continue
        (run / alias).mkdir(exist_ok=True)
        (run / alias / "report.json").write_text(
            json.dumps(
                {
                    "baseline_name": alias,
                    "judge_model_id": judge,
                    "n_sessions": n_sessions,
                    "overall_accuracy": 0.66,
                    "overall_ci_low": 0.55,
                    "overall_ci_high": 0.77,
                }
            )
        )
    return run, slice_sha


def _run_gate(run, slice_sha, *, allow_dev_judge=False, check_only=True):
    gate = _load_script("promote_lme_to_final")
    argv = sys.argv
    sys.argv = [
        "promote_lme_to_final.py",
        "--run-root",
        str(run),
        "--expected-slice-sha",
        slice_sha,
    ]
    if allow_dev_judge:
        sys.argv.append("--allow-dev-judge")
    if check_only:
        sys.argv.append("--check-only")
    try:
        return gate.main()
    finally:
        sys.argv = argv


def test_lme_gate_passes_clean_thesis_run(tmp_path: Path) -> None:
    run, sha = _make_lme_run(tmp_path, judge="gpt-4o")
    assert _run_gate(run, sha) == 0


@pytest.mark.parametrize(
    "kw,reason",
    [
        (dict(profile="light"), "non-thesis profile"),
        (dict(complete=False), "incomplete run"),
        (dict(synthetic=True), "synthetic slice"),
        (dict(drop_system="controller"), "missing system report"),
        (dict(clean_summary=False), "summary validation errors"),
        (dict(n_sessions=10), "truncated n_sessions"),
        (dict(judge="phi3.5:3.8b"), "dev judge without ack"),
    ],
)
def test_lme_gate_fails_loudly(tmp_path: Path, kw, reason) -> None:
    run, sha = _make_lme_run(tmp_path, **kw)
    assert _run_gate(run, sha) == 1, f"gate should FAIL on {reason}"
    assert not (run / "FINAL_OK.json").exists()


def test_lme_gate_wrong_slice_sha_fails(tmp_path: Path) -> None:
    run, _sha = _make_lme_run(tmp_path)
    assert _run_gate(run, "0" * 64) == 1


def test_lme_dev_judge_caps_at_final_candidate(tmp_path: Path) -> None:
    run, sha = _make_lme_run(tmp_path, judge="phi3.5:3.8b")
    # with ack: passes but ONLY as final-candidate (no FINAL_OK)
    assert _run_gate(run, sha, allow_dev_judge=True, check_only=False) == 0
    assert (run / "FINAL_CANDIDATE_OK.json").exists()
    assert not (run / "FINAL_OK.json").exists()
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["tier"] == "final-candidate"
    assert manifest["thesis_use"] == "final_candidate_dev_judge"


def test_lme_nondev_judge_promotes_to_final(tmp_path: Path) -> None:
    run, sha = _make_lme_run(tmp_path, judge="gpt-4o")
    assert _run_gate(run, sha, check_only=False) == 0
    assert (run / "FINAL_OK.json").exists()
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["tier"] == "final"


def test_mgp6_gate_refuses_limited_smoke_run(tmp_path: Path, capsys) -> None:
    """A --limit smoke run (tier=smoke) must never promote, even on thesis profile."""
    promote = _load_script("promote_to_final")
    run = tmp_path / "run"
    (run / "controller").mkdir(parents=True)
    (run / "b4").mkdir(parents=True)
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "model_profile": "thesis",
                "complete": True,
                "sanity_ok": True,
                "limit": 50,
                "tier": "smoke",
                "input": "data/mgp6_v1_seed0.jsonl",
            }
        )
    )
    (run / "sanity_report.json").write_text(json.dumps({"ok": True, "per_system": {}}))
    for alias in ("controller", "b4"):
        (run / alias / "predictions.jsonl").write_text("")
    argv = sys.argv
    sys.argv = [
        "promote_to_final.py",
        "--run-root",
        str(run),
        "--mgp6",
        str(_SCRIPTS.parent / "data" / "mgp6_v1_seed0.jsonl"),
        "--check-only",
    ]
    try:
        rc = promote.main()
    finally:
        sys.argv = argv
    out = capsys.readouterr().out
    assert rc == 1
    assert "[FAIL] full run (not smoke/limited)" in out
    assert not (run / "FINAL_OK.json").exists()
