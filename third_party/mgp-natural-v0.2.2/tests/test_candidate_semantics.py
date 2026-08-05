from __future__ import annotations

from pathlib import Path

import pytest

from mgp_natural.errors import ValidationError
from mgp_natural.mining.studychat import construct_candidate, mine_file
from mgp_natural.ontology.contract import validate_construction_item
from mgp_natural.util.io import iter_jsonl

ROWS = list(iter_jsonl(Path("data/fixtures/studychat_candidate_fixture.jsonl")))


def test_explicit_reaffirmation() -> None:
    item = construct_candidate(ROWS[0])
    assert item["constructor_provisional_action"] == "KEEP"
    assert item["constructor_provisional_resulting_value"] == item["prior_value"]


def test_explicit_correction() -> None:
    item = construct_candidate(ROWS[1])
    assert item["constructor_provisional_action"] == "SUPERSEDE"
    assert item["prior_value"] == "cleaned_dataset.csv"
    assert item["constructor_provisional_resulting_value"] == "final_cleaned_dataset.csv"


def test_uncertainty() -> None:
    item = construct_candidate(ROWS[2])
    assert item["constructor_provisional_action"] == "ABSTAIN"
    assert item["constructor_provisional_resulting_value"] == item["prior_value"]


def test_no_prior_state() -> None:
    item = construct_candidate(ROWS[3])
    assert item["rejection_reason"] == "NO_PRIOR_STATE"


def test_false_keyword_assignment_candidate() -> None:
    item = construct_candidate(ROWS[4])
    assert item["rejection_reason"] == "ASSIGNMENT_INSTRUCTION_ONLY"


def test_unrelated_acknowledgment() -> None:
    item = construct_candidate(ROWS[5])
    assert item["rejection_reason"] == "PURE_ACKNOWLEDGMENT"


def test_non_atomic_candidate() -> None:
    item = construct_candidate(ROWS[6])
    assert item["rejection_reason"] == "NON_ATOMIC_CANDIDATE"


def test_unresolved_resulting_value() -> None:
    item = construct_candidate(ROWS[7])
    assert item["rejection_reason"] == "RESULTING_VALUE_UNRESOLVED"


def test_no_stateful_content() -> None:
    item = construct_candidate(ROWS[8])
    assert item["rejection_reason"] == "NO_STATEFUL_CONTENT"


def test_slot_mismatch_validator_rejects_missing_prior_evidence(construction_item: dict, clone) -> None:
    item = clone(construction_item)
    item["prior_evidence_turn_ids"] = ["T003"]
    with pytest.raises(ValidationError, match="prior evidence must precede"):
        validate_construction_item(item)


def test_non_atomic_prior_is_rejected(construction_item: dict, clone) -> None:
    item = clone(construction_item)
    item["prior_value"] = "old.csv or backup.csv"
    with pytest.raises(ValidationError, match="atomic"):
        validate_construction_item(item)


def test_mining_writes_reason_coded_rejections(tmp_path: Path) -> None:
    report = mine_file(
        Path("data/fixtures/studychat_candidate_fixture.jsonl"),
        tmp_path / "candidates.jsonl",
        tmp_path / "rejections.jsonl",
        tmp_path / "report.json",
    )
    assert report["candidates"] >= 4
    assert report["publication_eligible"] is False
    assert report["rejection_reasons"]


def _reconstructed_chat(interactions: list[dict], *, status: str = "VALIDATED") -> dict:
    return {
        "schema_version": "1.0",
        "source_track": "STUDYCHAT",
        "source_user_private": "user-fixture",
        "source_chat_private": "chat-fixture",
        "topic_private": "fixture",
        "semester_private": "fixture",
        "interactions": [
            {
                "interaction_count": index,
                "prompt": row["prompt"],
                "response": row.get("response", f"response-{index}"),
                "row_indices_private": [index],
                "source_names_private": ["fixture"],
                "source_conflict_private": False,
            }
            for index, row in enumerate(interactions)
        ],
        "source_rows_private": list(range(len(interactions))),
        "observed_interaction_counts_private": list(range(len(interactions))),
        "missing_interaction_counts_private": [],
        "expected_total_interactions_private": len(interactions),
        "source_names_private": ["fixture"],
        "source_completeness": "COMPLETE_OBSERVED",
        "reconstruction_status": status,
    }


def _mine_reconstructed(tmp_path: Path, chat: dict) -> tuple[list[dict], list[dict], dict]:
    from mgp_natural.mining.studychat import mine_reconstructed_chats
    from mgp_natural.util.io import read_json, write_jsonl

    source = tmp_path / "chats.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    rejections = tmp_path / "rejections.jsonl"
    report = tmp_path / "report.json"
    write_jsonl(source, [chat])
    mine_reconstructed_chats(source, candidates, rejections, report)
    return list(iter_jsonl(candidates)), list(iter_jsonl(rejections)), read_json(report)


def test_reconstructed_miner_explicit_file_correction(tmp_path: Path) -> None:
    chat = _reconstructed_chat(
        [
            {"prompt": "Please use cleaned.csv."},
            {"prompt": "Use final.csv instead of cleaned.csv.", "response": "not exposed"},
        ]
    )
    candidates, _, _ = _mine_reconstructed(tmp_path, chat)
    assert len(candidates) == 1
    item = candidates[0]
    assert item["constructor_provisional_action"] == "SUPERSEDE"
    assert item["prior_value"] == "cleaned.csv"
    assert item["candidate_value"] == "final.csv"
    assert item["dialogue"][-1]["role"] == "user"
    assert all(turn["text"] != "not exposed" for turn in item["dialogue"])


def test_reconstructed_miner_file_reaffirmation(tmp_path: Path) -> None:
    chat = _reconstructed_chat(
        [
            {"prompt": "Please use cleaned.csv."},
            {"prompt": "Continue using cleaned.csv."},
        ]
    )
    candidates, _, _ = _mine_reconstructed(tmp_path, chat)
    assert candidates[0]["constructor_provisional_action"] == "KEEP"


def test_reconstructed_miner_uncertain_switch_abstains(tmp_path: Path) -> None:
    chat = _reconstructed_chat(
        [
            {"prompt": "Please use cleaned.csv."},
            {"prompt": "Maybe we should switch to final.csv."},
        ]
    )
    candidates, _, _ = _mine_reconstructed(tmp_path, chat)
    assert candidates[0]["constructor_provisional_action"] == "ABSTAIN"
    assert candidates[0]["constructor_provisional_resulting_value"] == "cleaned.csv"


def test_reconstructed_miner_conditional_file_reference_abstains(tmp_path: Path) -> None:
    chat = _reconstructed_chat(
        [
            {"prompt": "Here is my main.py."},
            {"prompt": "If this is my main.py, what should its output be?"},
        ]
    )
    candidates, _, _ = _mine_reconstructed(tmp_path, chat)
    assert candidates[0]["constructor_provisional_action"] == "ABSTAIN"


def test_reconstructed_miner_rejects_code_json_and_assignment_text(tmp_path: Path) -> None:
    chat = _reconstructed_chat(
        [
            {"prompt": "df.to_json('result.json')"},
            {
                "prompt": (
                    "## Part 4.1 GPT Data Manipulation: copy the output and ask the model "
                    "to convert it to a markdown table."
                )
            },
        ]
    )
    candidates, rejections, report = _mine_reconstructed(tmp_path, chat)
    assert candidates == []
    assert report["candidates"] == 0
    assert {row["rejection_reason"] for row in rejections} >= {
        "ASSIGNMENT_INSTRUCTION_ONLY",
    }


def test_reconstructed_miner_rejects_gap_between_prior_and_candidate(tmp_path: Path) -> None:
    from mgp_natural.mining.studychat import mine_reconstructed_chats
    from mgp_natural.util.io import read_json, write_jsonl

    chat = _reconstructed_chat(
        [
            {"prompt": "Please use cleaned.csv."},
            {"prompt": "irrelevant placeholder"},
            {"prompt": "Use final.csv instead of cleaned.csv."},
        ]
    )
    chat["interactions"] = [chat["interactions"][0], chat["interactions"][2]]
    chat["interactions"][1]["interaction_count"] = 2
    chat["observed_interaction_counts_private"] = [0, 2]
    chat["missing_interaction_counts_private"] = [1]
    chat["source_completeness"] = "PARTIAL_AVAILABLE"
    chat["reconstruction_status"] = "PARTIAL_WITH_RECORDED_GAPS"
    source = tmp_path / "gap.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    rejections = tmp_path / "rejections.jsonl"
    report = tmp_path / "report.json"
    write_jsonl(source, [chat])
    mine_reconstructed_chats(source, candidates, rejections, report)
    assert list(iter_jsonl(candidates)) == []
    assert read_json(report)["rejection_reasons"]["SOURCE_INCOMPLETE"] == 1

