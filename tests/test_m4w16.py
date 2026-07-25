from __future__ import annotations

import json

from ask.eval.m4w16 import audit_patterns, decide_g3, run_m4w16, validate_artifacts


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _prediction(scenario_id, scenario_type, gold, predicted, correct):
    return {
        "scenario_id": scenario_id,
        "scenario_type": scenario_type,
        "initial_memory_type": "stable_pref",
        "gold_action": gold,
        "predicted_action": predicted,
        "correct_action": correct,
        "state_correct": correct,
    }


def _report(alias, *, controller=False):
    predictions = [
        _prediction("s1", "T1", "SUPERSEDE", "SUPERSEDE" if controller else "KEEP", controller),
        _prediction("s2", "T4", "ABSTAIN", "KEEP", False),
        _prediction("s3", "T5", "KEEP", "KEEP", True),
        _prediction("s4", "T6", "ABSTAIN", "ABSTAIN", True),
    ]
    per_type = {
        "T1": {"action_accuracy": 1.0 if controller else 0.0},
        "T2": {"action_accuracy": 0.0},
        "T3": {"action_accuracy": 0.0},
        "T4": {"action_accuracy": 0.0},
        "T5": {"action_accuracy": 1.0},
        "T6": {"action_accuracy": 1.0},
    }
    return {
        "baseline": "controller" if controller else alias,
        "n_scenarios": 60,
        "action_accuracy": 0.75 if controller else 0.5,
        "per_type": per_type,
        "threshold_ordering": {
            "confirmed": True,
            "empirical_status": "confirmed",
            "mean_theta_sup_by_candidate_type": {
                "stable_pref": 0.9,
                "episodic_fact": 0.75,
                "transient_pref": 0.55,
            },
            "errors_by_candidate_type": {"stable_pref": 1},
            "n_by_candidate_type": {"stable_pref": 4, "episodic_fact": 2, "transient_pref": 1},
        },
        "predictions": predictions if controller else [],
    }


def _log(scenario_id, action, *, r=-1.0, s_abs=0.0):
    return {
        "id": 1,
        "session_id": scenario_id,
        "action": action,
        "candidate_text": "User now prefers tea.",
        "candidate_type": "stable_pref",
        "feature_c": 1.0,
        "feature_e": 1.0,
        "feature_f": 0.0,
        "feature_r": r,
        "feature_rho": 0.9,
        "s_rev": 1.05,
        "s_abs": s_abs,
        "theta_sup": 0.9,
        "theta_abs": 0.6,
        "rationale": "S_rev=1.050 above theta; S_abs=0.000 below theta; supersede.",
    }


def _populate_fixture(tmp_path):
    m4w14 = tmp_path / "runs" / "m4w14"
    m4w15 = tmp_path / "runs" / "m4w15"
    for alias in ("b1", "b2", "b3", "b4"):
        _write_json(m4w14 / alias / "mgp6_report.json", _report(alias))
    _write_json(m4w14 / "controller" / "mgp6_report.json", _report("controller", controller=True))
    _write_jsonl(
        m4w14 / "controller" / "action_log.jsonl",
        [
            _log("s1", "Supersede"),
            _log("s2", "Keep", r=0.0),
            _log("s3", "Keep", r=0.0),
            _log("s4", "Abstain", r=0.0, s_abs=1.0),
        ],
    )
    for idx in range(21):
        threshold = idx / 20
        base = m4w15 / "sweep" / f"threshold_{threshold:.2f}"
        _write_json(base / "report.json", {"threshold": threshold})
        _write_jsonl(base / "mgp6" / "controller" / "action_log.jsonl", [_log("s1", "Supersede")])
        _write_jsonl(base / "longmemeval" / "controller" / "action_log.jsonl", [_log("l1", "Keep", r=0.0)])
    mgp6_input = tmp_path / "data" / "mgp6.jsonl"
    _write_jsonl(
        mgp6_input,
        [
            {
                "scenario_id": "s1",
                "type": "T1",
                "initial_memory_state": [{"type": "stable_pref"}],
                "perturbation_event": "now tea",
                "rationale_notes": "clean drift",
            },
            {
                "scenario_id": "s2",
                "type": "T4",
                "initial_memory_state": [{"type": "stable_pref"}],
                "perturbation_event": "maybe",
                "rationale_notes": "ambiguous",
            },
            {
                "scenario_id": "s3",
                "type": "T5",
                "initial_memory_state": [{"type": "stable_pref"}],
                "perturbation_event": "tonight",
                "rationale_notes": "transient",
            },
            {
                "scenario_id": "s4",
                "type": "T6",
                "initial_memory_state": [{"type": "stable_pref"}],
                "perturbation_event": "noisy",
                "rationale_notes": "low confidence",
            },
        ],
    )
    return m4w14, m4w15, mgp6_input


def test_validate_artifacts_reports_missing(tmp_path):
    status = validate_artifacts(
        m4w14_root=tmp_path / "m4w14",
        m4w15_root=tmp_path / "m4w15",
        mgp6_input=tmp_path / "mgp6.jsonl",
    )

    assert not status.ok
    assert "Missing required" in status.format()


def test_audit_patterns_and_g3_pass():
    reports = {"controller": _report("controller", controller=True), "b4": _report("b4")}
    for alias in ("b1", "b2", "b3"):
        reports[alias] = _report(alias)

    audit = audit_patterns(reports)
    g3 = decide_g3(reports)

    assert audit["controller_t5_t6_abstain"]["T6"]["always_abstain"]
    assert g3["decision"] == "PASS"
    assert "T1" in g3["passing_types"]


def test_run_m4w16_writes_deliverables(tmp_path):
    m4w14, m4w15, mgp6_input = _populate_fixture(tmp_path)

    result = run_m4w16(
        m4w14_root=m4w14,
        m4w15_root=m4w15,
        mgp6_input=mgp6_input,
        notes_dir=tmp_path / "NOTES",
        out_dir=tmp_path / "runs" / "m4w16",
    )

    assert result["g3"]["decision"] == "PASS"
    assert (tmp_path / "NOTES" / "m4w16_qualitative.md").exists()
    assert (tmp_path / "NOTES" / "m4w16_threshold_validation.md").exists()
    assert (tmp_path / "NOTES" / "G3_gate_decision.md").exists()
    taxonomy = tmp_path / "runs" / "m4w16" / "error_taxonomy.csv"
    assert taxonomy.exists()
    assert "extraction_error" in taxonomy.read_text(encoding="utf-8")
