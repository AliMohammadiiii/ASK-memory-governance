"""Public-only loading, prediction validation, and scoring for MGP-6 v4.3.

The released train/dev JSONL contains ``gold_action`` for supervised development
and scoring.  This module deliberately removes it (and every other prohibited
field) before records are rendered into model prompts or raw-response logs.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

VALID_ACTIONS = ("KEEP", "SUPERSEDE", "ABSTAIN")
PROHIBITED_MODEL_KEYS = frozenset(
    {
        "gold_action",
        "design_target",
        "source_item_id",
        "component_id",
        "private_item_id",
        "annotator_id",
        "final_consensus",
        "human_gold",
        "hidden_gold",
    }
)
MODEL_INPUT_KEYS = ("public_id", "memory_before", "dialogue", "evaluation_query")


class MGP6V43Error(ValueError):
    """Raised when a release, prediction, or model-facing object is invalid."""


class MGP6V43Record(BaseModel):
    """One public train/dev release record, including its development label."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    public_id: str = Field(pattern=r"^MGP43-[0-9A-F]{20}$")
    memory_before: dict[str, Any]
    dialogue: list[Any]
    evaluation_query: str
    gold_action: Literal["KEEP", "SUPERSEDE", "ABSTAIN"] | None = None

    def model_input(self) -> dict[str, Any]:
        """Return the only object that may be rendered into a model prompt."""
        payload = {
            "public_id": self.public_id,
            "memory_before": self.memory_before,
            "dialogue": self.dialogue,
            "evaluation_query": self.evaluation_query,
        }
        assert_model_safe(payload)
        return payload


class MGP6V43Prediction(BaseModel):
    """Strict public prediction format required by the v4.3 protocol."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    public_id: str = Field(pattern=r"^MGP43-[0-9A-F]{20}$")
    action: Literal["KEEP", "SUPERSEDE", "ABSTAIN"]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def assert_model_safe(value: Any) -> None:
    prohibited = sorted(set(_walk_keys(value)) & PROHIBITED_MODEL_KEYS)
    if prohibited:
        raise MGP6V43Error(f"model-facing payload contains prohibited fields: {prohibited}")


def load_public_records(path: str | Path, *, require_gold: bool = True) -> list[MGP6V43Record]:
    """Load a public split in deterministic public-ID order."""
    records: list[MGP6V43Record] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = MGP6V43Record.model_validate_json(line)
        except Exception as exc:  # Pydantic supplies the useful validation detail.
            raise MGP6V43Error(f"{path}:{line_no}: invalid public record") from exc
        if require_gold and record.gold_action is None:
            raise MGP6V43Error(f"{path}:{line_no}: missing development gold_action")
        records.append(record)
    ids = [record.public_id for record in records]
    duplicates = sorted(item_id for item_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise MGP6V43Error(f"duplicate public IDs: {duplicates[:10]}")
    return sorted(records, key=lambda record: record.public_id)


def validate_public_release(train: list[MGP6V43Record], dev: list[MGP6V43Record], facts: Mapping[str, Any]) -> None:
    """Validate public facts without inspecting private component assignments."""
    expected = facts["split_counts"]
    if len(train) != expected["train"] or len(dev) != expected["dev"]:
        raise MGP6V43Error("public split count does not match RELEASE_FACTS.json")
    overlap = {row.public_id for row in train} & {row.public_id for row in dev}
    if overlap:
        raise MGP6V43Error(f"public ID appears in train and dev: {sorted(overlap)[:10]}")
    for split_name, records in (("train", train), ("dev", dev)):
        distribution = Counter(record.gold_action for record in records)
        if distribution != Counter(facts["class_distribution"][split_name]):
            raise MGP6V43Error(f"{split_name} class balance does not match release facts")


def validate_component_splits(component_to_split: Mapping[str, str]) -> None:
    """Validate a private/audit component map without making it model-facing."""
    allowed = {"train", "dev", "hidden"}
    if not component_to_split or set(component_to_split.values()) - allowed:
        raise MGP6V43Error("invalid component split map")
    # A mapping is keyed by component, so duplicate component assignment is impossible;
    # explicit counting nevertheless makes the expected 20/20/60 invariant testable.
    counts = Counter(component_to_split.values())
    if counts != Counter({"train": 20, "dev": 20, "hidden": 60}):
        raise MGP6V43Error("component split counts must be 20/20/60")


def build_decision_prompt(record: MGP6V43Record, system_prompt: str) -> str:
    """Build a deterministic, label-free action prompt."""
    payload = record.model_input()
    return (
        f"{system_prompt.strip()}\n\n"
        "Decide exactly one action from KEEP, SUPERSEDE, ABSTAIN. "
        "Return JSON only: {\"action\":\"KEEP\"}.\n\n"
        f"INPUT={canonical_json(payload)}"
    )


def parse_action_response(raw_response: str) -> str:
    """Parse either the required JSON object or a bare allowed action."""
    candidate = raw_response.strip()
    if candidate in VALID_ACTIONS:
        return candidate
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise MGP6V43Error("response is not an action or JSON action object") from exc
    try:
        return MGP6V43Prediction.model_validate({"public_id": "MGP43-00000000000000000000", **value}).action
    except Exception as exc:
        raise MGP6V43Error("response does not contain a valid action") from exc


def load_predictions(path: str | Path, expected_ids: Iterable[str]) -> list[MGP6V43Prediction]:
    """Load strict prediction JSONL and reject duplicate, unknown, or missing IDs."""
    expected = set(expected_ids)
    predictions: list[MGP6V43Prediction] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            predictions.append(MGP6V43Prediction.model_validate_json(line))
        except Exception as exc:
            raise MGP6V43Error(f"{path}:{line_no}: invalid prediction") from exc
    ids = [prediction.public_id for prediction in predictions]
    duplicates = sorted(item_id for item_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise MGP6V43Error(f"duplicate prediction IDs: {duplicates[:10]}")
    found = set(ids)
    unknown, missing = sorted(found - expected), sorted(expected - found)
    if unknown or missing:
        raise MGP6V43Error(f"prediction coverage mismatch: unknown={unknown[:10]} missing={missing[:10]}")
    return sorted(predictions, key=lambda prediction: prediction.public_id)


def write_prediction_resume_safe(path: str | Path, prediction: MGP6V43Prediction) -> bool:
    """Append exactly once; reject any conflicting resume record and fsync the write."""
    output = Path(path)
    existing: dict[str, MGP6V43Prediction] = {}
    if output.exists():
        for record in load_predictions_allow_partial(output):
            existing[record.public_id] = record
    previous = existing.get(prediction.public_id)
    if previous is not None:
        if previous != prediction:
            raise MGP6V43Error(f"conflicting resumed prediction for {prediction.public_id}")
        return False
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(prediction.model_dump()) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return True


def load_predictions_allow_partial(path: str | Path) -> list[MGP6V43Prediction]:
    records: list[MGP6V43Prediction] = []
    seen: set[str] = set()
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = MGP6V43Prediction.model_validate_json(line)
        except Exception as exc:
            raise MGP6V43Error(f"{path}:{line_no}: invalid prediction") from exc
        if record.public_id in seen:
            raise MGP6V43Error(f"{path}:{line_no}: duplicate resumed prediction")
        seen.add(record.public_id)
        records.append(record)
    return records


def write_raw_response(path: str | Path, *, public_id: str, raw_response: str, metadata: Mapping[str, Any]) -> None:
    """Persist a label-free raw response record with explicit operational accounting."""
    row = {"public_id": public_id, "raw_response": raw_response, **dict(metadata)}
    assert_model_safe(row)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(row) + "\n")


def _per_class(confusion: Mapping[str, Mapping[str, int]]) -> dict[str, dict[str, float | int]]:
    output: dict[str, dict[str, float | int]] = {}
    for label in VALID_ACTIONS:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in VALID_ACTIONS if other != label)
        fn = sum(confusion[label][other] for other in VALID_ACTIONS if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        output[label] = {
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "support": sum(confusion[label].values()),
        }
    return output


def score_actions(gold: Mapping[str, str], predictions: Mapping[str, str]) -> dict[str, Any]:
    if set(gold) != set(predictions):
        raise MGP6V43Error("cannot score mismatched ID coverage")
    confusion = {actual: {predicted: 0 for predicted in VALID_ACTIONS} for actual in VALID_ACTIONS}
    for public_id in sorted(gold):
        confusion[gold[public_id]][predictions[public_id]] += 1
    per_class = _per_class(confusion)
    n = len(gold)
    accuracy = sum(confusion[label][label] for label in VALID_ACTIONS) / n if n else 0.0
    return {
        "n_items": n,
        "accuracy": accuracy,
        "macro_f1": sum(float(per_class[label]["f1"]) for label in VALID_ACTIONS) / len(VALID_ACTIONS),
        "per_class": per_class,
        "confusion_matrix": confusion,
        "coverage": 1.0,
    }


def cluster_bootstrap(
    gold: Mapping[str, str], predictions: Mapping[str, str], component_by_id: Mapping[str, str], *, seed: int = 4301, replicates: int = 5000
) -> dict[str, Any]:
    """Component-cluster bootstrap for scoring contexts that have a private map."""
    if set(gold) != set(component_by_id):
        raise MGP6V43Error("component map does not cover the scored IDs")
    by_component: dict[str, list[str]] = defaultdict(list)
    for public_id, component in component_by_id.items():
        by_component[component].append(public_id)
    rng, components = random.Random(seed), sorted(by_component)
    accuracies: list[float] = []
    macro_f1s: list[float] = []
    for _ in range(replicates):
        sampled_ids = [public_id for component in (rng.choice(components) for _ in components) for public_id in by_component[component]]
        sample_gold = {f"{index}:{public_id}": gold[public_id] for index, public_id in enumerate(sampled_ids)}
        sample_predictions = {f"{index}:{public_id}": predictions[public_id] for index, public_id in enumerate(sampled_ids)}
        result = score_actions(sample_gold, sample_predictions)
        accuracies.append(result["accuracy"])
        macro_f1s.append(result["macro_f1"])
    accuracies.sort()
    macro_f1s.sort()
    low, high = int(0.025 * replicates), int(0.975 * replicates) - 1
    return {
        "seed": seed,
        "replicates": replicates,
        "accuracy": [accuracies[low], accuracies[high]],
        "macro_f1": [macro_f1s[low], macro_f1s[high]],
    }
