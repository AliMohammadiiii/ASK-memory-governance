"""Privacy-review support that records indicators without claiming anonymity."""
from __future__ import annotations

import csv
import hashlib
import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from mgp_natural.util.io import iter_jsonl, write_json, write_jsonl


@dataclass(frozen=True)
class NerSpan:
    start: int
    end: int
    label: str
    score: float | None = None


class NerDetector(Protocol):
    def __call__(self, text: str) -> Sequence[NerSpan]: ...


class SpacyNerDetector:
    """Optional spaCy bridge loaded only after an explicit configuration choice."""

    def __init__(self, model: str) -> None:
        try:
            import spacy
        except ImportError as exc:
            from mgp_natural.errors import ValidationError

            raise ValidationError(
                "spaCy is not installed; install an explicitly approved NER dependency and model"
            ) from exc
        try:
            self._nlp = spacy.load(model)
        except Exception as exc:
            from mgp_natural.errors import ValidationError

            raise ValidationError(f"unable to load configured spaCy model: {model}") from exc

    def __call__(self, text: str) -> Sequence[NerSpan]:
        document = self._nlp(text)
        return [
            NerSpan(start=entity.start_char, end=entity.end_char, label=entity.label_)
            for entity in document.ents
        ]


def build_ner_detector(backend: str, model: str | None = None) -> NerDetector | None:
    normalized = backend.casefold().strip()
    if normalized in {"", "none", "disabled"}:
        return None
    if normalized == "spacy":
        if not model:
            from mgp_natural.errors import ValidationError

            raise ValidationError("--ner-model is required for the spaCy backend")
        return SpacyNerDetector(model)
    from mgp_natural.errors import ValidationError

    raise ValidationError(f"unsupported NER backend: {backend}")


@dataclass(frozen=True)
class PatternSpec:
    name: str
    regex: re.Pattern[str]
    severity: str


PATTERNS: tuple[PatternSpec, ...] = (
    PatternSpec(
        "EMAIL",
        re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
        "HIGH",
    ),
    PatternSpec(
        "IP_ADDRESS",
        re.compile(
            r"(?<!\d)(?:25[0-5]|2[0-4]\d|1?\d?\d)"
            r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)"
        ),
        "HIGH",
    ),
    PatternSpec("URL", re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>]+"), "MEDIUM"),
    PatternSpec(
        "API_TOKEN",
        re.compile(
            r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b"
        ),
        "CRITICAL",
    ),
    PatternSpec(
        "UNIX_PATH",
        re.compile(r"(?<!\w)/(?:Users|home|var|tmp|opt|srv|mnt|etc)/[^\s\"']+"),
        "HIGH",
    ),
    PatternSpec(
        "WINDOWS_PATH",
        re.compile(r"(?i)\b[A-Z]:\\(?:[^\\\s]+\\)*[^\\\s]+"),
        "HIGH",
    ),
    PatternSpec(
        "PRECISE_TIMESTAMP",
        re.compile(
            r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}"
            r"(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?\b"
        ),
        "MEDIUM",
    ),
    PatternSpec(
        "USERNAME",
        re.compile(r"(?<!\w)@[A-Za-z0-9_][A-Za-z0-9_.-]{2,31}\b"),
        "MEDIUM",
    ),
    PatternSpec(
        "REPOSITORY",
        re.compile(r"(?i)\b(?:github\.com|gitlab\.com)/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"),
        "MEDIUM",
    ),
    PatternSpec(
        "COURSE_ID",
        re.compile(r"(?i)\b(?:COMPSCI|CS|CSE|EECS)\s*[- ]?\d{2,4}[A-Z]?\b"),
        "MEDIUM",
    ),
    PatternSpec(
        "ASSIGNMENT_ID",
        re.compile(r"(?i)\b(?:assignment|homework|project|lab)\s*#?\s*\d+[A-Za-z]?\b"),
        "MEDIUM",
    ),
    PatternSpec(
        "GRADE_OR_SUBMISSION",
        re.compile(
            r"(?i)\b(?:grade|score|submission)\s*(?:is|:|=)?\s*"
            r"(?:\d{1,3}(?:\.\d+)?%?|[A-F][+-]?)\b"
        ),
        "HIGH",
    ),
    PatternSpec(
        "INSTRUCTOR_OR_STUDENT_NAME",
        re.compile(
            r"\b(?:Professor|Instructor|Teaching\s+Assistant|TA|Dr\.)\s+"
            r"[A-Z][A-Za-z'\u2019-]+(?:\s+[A-Z][A-Za-z'\u2019-]+){0,2}\b"
        ),
        "HIGH",
    ),
    PatternSpec(
        "INSTITUTIONAL_IDENTIFIER",
        re.compile(
            r"(?i)\b(?:student|employee|campus|university|net)\s*"
            r"(?:id|identifier|number)\s*(?:is|:|=)?\s*[A-Za-z0-9_-]{4,}\b"
        ),
        "HIGH",
    ),
    PatternSpec(
        "INSTITUTION_NAME",
        re.compile(
            r"\b(?:University\s+of\s+[A-Z][A-Za-z&'\u2019-]+(?:\s+[A-Z][A-Za-z&'\u2019-]+){0,3}|"
            r"[A-Z][A-Za-z&'\u2019-]+(?:\s+[A-Z][A-Za-z&'\u2019-]+){0,3}\s+University)\b"
        ),
        "MEDIUM",
    ),
)
SECRET_CHUNK = re.compile(r"\b[A-Za-z0-9+/=_-]{24,}\b")
IDENTITY_FIELD = re.compile(
    r"(?i)(?:^|\.)(?:user(?:name|_?id)?|author|contributor|student|instructor|owner|email|name)$"
)
SENSITIVE_FIELD = re.compile(
    r"(?i)(?:deleted|suppressed|oversight|revision_deleted|sensitive|private_content)"
)


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _string_fields(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _string_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _string_fields(child, f"{path}[{index}]")


def _finding(
    category: str,
    severity: str,
    location: str,
    token: str,
    start: int = 0,
    end: int | None = None,
) -> dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "location": location,
        "offset_start": start,
        "offset_end": len(token) if end is None else end,
        "match_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        "match_length": len(token),
    }


def scan_text(
    text: str,
    location: str,
    known_identity_tokens: Sequence[str] = (),
    ner_detector: NerDetector | None = None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if text and IDENTITY_FIELD.search(location):
        findings.append(_finding("IDENTITY_BEARING_FIELD", "HIGH", location, text))
    if text and SENSITIVE_FIELD.search(location):
        findings.append(_finding("SENSITIVE_SOURCE_FIELD", "CRITICAL", location, text))
    known_spans: list[tuple[int, int]] = []
    for token in sorted({value for value in known_identity_tokens if value}, key=len, reverse=True):
        for match in re.finditer(re.escape(token), text, re.IGNORECASE):
            known_spans.append((match.start(), match.end()))
            findings.append(
                _finding(
                    "KNOWN_IDENTITY_TOKEN",
                    "HIGH",
                    location,
                    match.group(0),
                    match.start(),
                    match.end(),
                )
            )
    for spec in PATTERNS:
        for match in spec.regex.finditer(text):
            if any(match.start() < end and match.end() > start for start, end in known_spans):
                continue
            findings.append(
                _finding(
                    spec.name,
                    spec.severity,
                    location,
                    match.group(0),
                    match.start(),
                    match.end(),
                )
            )
    for match in SECRET_CHUNK.finditer(text):
        token = match.group(0)
        if shannon_entropy(token) >= 4.0 and not token.isdigit():
            findings.append(
                _finding(
                    "HIGH_ENTROPY_SECRET_LIKE",
                    "HIGH",
                    location,
                    token,
                    match.start(),
                    match.end(),
                )
            )
    if ner_detector is not None:
        severity_by_label = {
            "PERSON": "HIGH",
            "PER": "HIGH",
            "ORG": "MEDIUM",
            "GPE": "MEDIUM",
            "LOC": "MEDIUM",
            "FAC": "MEDIUM",
        }
        for entity in ner_detector(text):
            if entity.start < 0 or entity.end > len(text) or entity.start >= entity.end:
                continue
            label = re.sub(r"[^A-Za-z0-9]+", "_", entity.label.upper()).strip("_") or "ENTITY"
            token = text[entity.start : entity.end]
            finding = _finding(
                f"NER_{label}",
                severity_by_label.get(label, "MEDIUM"),
                location,
                token,
                entity.start,
                entity.end,
            )
            if entity.score is not None:
                finding["detector_score"] = float(entity.score)
            findings.append(finding)
    return findings


def scan_jsonl(
    input_path: Path,
    findings_path: Path,
    report_path: Path,
    queue_path: Path,
    known_identity_tokens: Sequence[str] = (),
    ner_detector: NerDetector | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    reviewed_rows = 0
    for row_index, row in enumerate(iter_jsonl(input_path), 1):
        reviewed_rows += 1
        item_id = str(row.get("item_id") or row.get("row_index") or row_index)
        review_id = hashlib.sha256(item_id.encode("utf-8")).hexdigest()[:20]
        for location, text in _string_fields(row):
            for finding in scan_text(
                text, location, known_identity_tokens, ner_detector=ner_detector
            ):
                finding["record_id_private"] = item_id
                finding["review_id"] = review_id
                findings.append(finding)
    write_jsonl(findings_path, findings, mode=0o600)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with queue_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "review_id",
                "category",
                "severity",
                "finding_count",
                "review_status",
                "reviewer_notes",
            ],
        )
        writer.writeheader()
        grouped = Counter(
            (finding["review_id"], finding["category"], finding["severity"])
            for finding in findings
        )
        for (review_id, category, severity), count in sorted(grouped.items()):
            writer.writerow(
                {
                    "review_id": review_id,
                    "category": category,
                    "severity": severity,
                    "finding_count": count,
                    "review_status": "PENDING_HUMAN_REVIEW",
                    "reviewer_notes": "",
                }
            )
    report = {
        "schema_version": "1.0",
        "records_scanned": reviewed_rows,
        "findings": len(findings),
        "records_with_findings": len({finding["review_id"] for finding in findings}),
        "categories": dict(Counter(finding["category"] for finding in findings)),
        "severity": dict(Counter(finding["severity"] for finding in findings)),
        "manual_review_required": True,
        "manual_queue_rows": len(
            {
                (finding["review_id"], finding["category"], finding["severity"])
                for finding in findings
            }
        ),
        "anonymity_guaranteed": False,
        "ner_backend_enabled": ner_detector is not None,
        "status": "AUTOMATED_REVIEW_SUPPORT_COMPLETE_HUMAN_REVIEW_PENDING",
    }
    write_json(report_path, report)
    return report

