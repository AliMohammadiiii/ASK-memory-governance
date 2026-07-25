"""Agreement scoring for the M3-W12 advisor subsample."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .mgp6_schema import MGP6AdvisorAnnotation, MGP6Scenario, load_mgp6_jsonl

FIELDS = ("gold_action", "gold_memory_state", "expected_answer")


@dataclass(frozen=True)
class FieldAgreement:
    scenario_id: str
    scenario_type: str
    field: str
    agree: bool
    student_value: str
    advisor_value: str


def load_advisor_annotations(path: str | Path) -> dict[str, MGP6AdvisorAnnotation]:
    rows: dict[str, MGP6AdvisorAnnotation] = {}
    with Path(path).open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                annotation = MGP6AdvisorAnnotation.model_validate(json.loads(line))
            except Exception as exc:
                raise ValueError(f"line {line_no}: invalid advisor annotation: {exc}") from exc
            if annotation.scenario_id in rows:
                raise ValueError(f"duplicate advisor annotation: {annotation.scenario_id}")
            rows[annotation.scenario_id] = annotation
    return rows


def score_agreement(
    student_scenarios: list[MGP6Scenario],
    advisor_annotations: dict[str, MGP6AdvisorAnnotation],
) -> list[FieldAgreement]:
    out: list[FieldAgreement] = []
    for scenario in student_scenarios:
        advisor = advisor_annotations.get(scenario.scenario_id)
        if advisor is None:
            raise ValueError(f"missing advisor annotation for {scenario.scenario_id}")
        out.append(
            FieldAgreement(
                scenario_id=scenario.scenario_id,
                scenario_type=scenario.type,
                field="gold_action",
                agree=scenario.gold_action == advisor.gold_action,
                student_value=scenario.gold_action,
                advisor_value=advisor.gold_action,
            )
        )
        student_memory = _memory_text_set(scenario.gold_memory_state)
        advisor_memory = _memory_text_set(advisor.gold_memory_state)
        out.append(
            FieldAgreement(
                scenario_id=scenario.scenario_id,
                scenario_type=scenario.type,
                field="gold_memory_state",
                agree=student_memory == advisor_memory,
                student_value=" | ".join(sorted(student_memory)),
                advisor_value=" | ".join(sorted(advisor_memory)),
            )
        )
        out.append(
            FieldAgreement(
                scenario_id=scenario.scenario_id,
                scenario_type=scenario.type,
                field="expected_answer",
                agree=_answer_match(scenario.expected_answer, advisor.expected_answer),
                student_value=scenario.expected_answer,
                advisor_value=advisor.expected_answer,
            )
        )
    return out


def write_agreement_csv(rows: list[FieldAgreement], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "row_type",
                "scope",
                "group",
                "scenario_id",
                "type",
                "field",
                "agree",
                "n",
                "agreement",
                "student_value",
                "advisor_value",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "row_type": "detail",
                    "scope": "item",
                    "group": row.scenario_id,
                    "scenario_id": row.scenario_id,
                    "type": row.scenario_type,
                    "field": row.field,
                    "agree": int(row.agree),
                    "n": 1,
                    "agreement": f"{1.0 if row.agree else 0.0:.6f}",
                    "student_value": row.student_value,
                    "advisor_value": row.advisor_value,
                }
            )
        for scope, group, field, subset in _summary_groups(rows):
            n = len(subset)
            agree = sum(1 for row in subset if row.agree)
            writer.writerow(
                {
                    "row_type": "summary",
                    "scope": scope,
                    "group": group,
                    "scenario_id": "",
                    "type": group if scope == "type" else "",
                    "field": field,
                    "agree": agree,
                    "n": n,
                    "agreement": f"{(agree / n) if n else 0.0:.6f}",
                    "student_value": "",
                    "advisor_value": "",
                }
            )


def compute_agreement_csv(
    *,
    student_path: str | Path,
    advisor_path: str | Path,
    selected_ids: set[str] | None,
    out_path: str | Path,
) -> list[FieldAgreement]:
    scenarios = load_mgp6_jsonl(student_path)
    if selected_ids is not None:
        scenarios = [scenario for scenario in scenarios if scenario.scenario_id in selected_ids]
    annotations = load_advisor_annotations(advisor_path)
    rows = score_agreement(scenarios, annotations)
    write_agreement_csv(rows, out_path)
    return rows


def _summary_groups(rows: list[FieldAgreement]):
    yield ("overall", "all", "all", rows)
    by_type: dict[str, list[FieldAgreement]] = defaultdict(list)
    by_field: dict[str, list[FieldAgreement]] = defaultdict(list)
    by_type_field: dict[tuple[str, str], list[FieldAgreement]] = defaultdict(list)
    for row in rows:
        by_type[row.scenario_type].append(row)
        by_field[row.field].append(row)
        by_type_field[(row.scenario_type, row.field)].append(row)
    for scenario_type in sorted(by_type):
        yield ("type", scenario_type, "all", by_type[scenario_type])
    for field in FIELDS:
        yield ("field", "all", field, by_field[field])
    for (scenario_type, field), subset in sorted(by_type_field.items()):
        yield ("type_field", scenario_type, field, subset)


def _memory_text_set(items) -> set[str]:  # noqa: ANN001
    return {_normalize(item.text) for item in items}


def _answer_match(student: str, advisor: str) -> bool:
    a = _normalize(student)
    b = _normalize(advisor)
    if not a or not b:
        return False
    return a in b or b in a


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
