from __future__ import annotations

from pathlib import Path

import pytest

from mgp_natural.privacy.redaction import redact_jsonl, redact_text
from mgp_natural.privacy.scanner import scan_jsonl, scan_text
from mgp_natural.util.io import write_jsonl


def _token_fixture() -> str:
    """Build a secret-shaped value at runtime without embedding one in source."""

    return "sk-" + ("a" * 26) + "123456"


@pytest.mark.parametrize(
    "text,category",
    [
        ("contact student@example.edu", "EMAIL"),
        ("server 192.168.10.4", "IP_ADDRESS"),
        ("see https://example.org/path", "URL"),
        ("open /home/alice/private/data.csv", "UNIX_PATH"),
        (r"open C:\Users\Alice\secret.txt", "WINDOWS_PATH"),
        ("token " + _token_fixture(), "API_TOKEN"),
        ("user @specific_username", "USERNAME"),
        ("repo github.com/private-owner/private-repo", "REPOSITORY"),
        ("at 2026-08-04T01:23:45Z", "PRECISE_TIMESTAMP"),
        ("course CS 501", "COURSE_ID"),
        ("assignment 12", "ASSIGNMENT_ID"),
        ("grade: 93%", "GRADE_OR_SUBMISSION"),
    ],
)
def test_privacy_patterns(text: str, category: str) -> None:
    assert category in {finding["category"] for finding in scan_text(text, "$.text")}


def test_high_entropy_secret() -> None:
    text = "credential qD7xA9vB2mN5pR8sT1wY4zC6kL0jH3fG"
    categories = {finding["category"] for finding in scan_text(text, "$.text")}
    assert "HIGH_ENTROPY_SECRET_LIKE" in categories


def test_known_identity_token() -> None:
    findings = scan_text("Ask Professor UniqueName about it", "$.text", known_identity_tokens=["Professor UniqueName"])
    assert {item["category"] for item in findings} == {"KNOWN_IDENTITY_TOKEN"}


def test_redaction_does_not_log_raw_string() -> None:
    original = f"email student@example.edu and token {_token_fixture()}"
    redacted, events = redact_text(original)
    assert "student@example.edu" not in redacted
    assert "sk-" not in redacted
    assert all("student@example.edu" not in str(event) for event in events)


def test_scan_and_redaction_reports_are_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    write_jsonl(source, [{"item_id": "i1", "dialogue": [{"text": "mail a@example.org"}]}])
    report = scan_jsonl(
        source,
        tmp_path / "findings.jsonl",
        tmp_path / "report.json",
        tmp_path / "queue.csv",
    )
    assert report["manual_review_required"] is True
    assert report["anonymity_guaranteed"] is False
    redaction = redact_jsonl(
        source,
        tmp_path / "redacted.jsonl",
        tmp_path / "log.jsonl",
        tmp_path / "summary.json",
    )
    assert redaction["manual_review_required"] is True
    assert redaction["anonymity_guaranteed"] is False


def test_configurable_ner_review_support_hashes_entity() -> None:
    from mgp_natural.privacy.scanner import NerSpan

    def detector(text: str) -> list[NerSpan]:
        start = text.index("Example Person")
        return [NerSpan(start=start, end=start + len("Example Person"), label="PERSON", score=0.91)]

    findings = scan_text("Ask Example Person tomorrow", "$.text", ner_detector=detector)
    entity = next(item for item in findings if item["category"] == "NER_PERSON")
    assert entity["severity"] == "HIGH"
    assert entity["detector_score"] == 0.91
    assert "Example Person" not in str(entity)
