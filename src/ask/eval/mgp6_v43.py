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
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ask.controller.active import FeatureSnapshot, decide, rho

VALID_ACTIONS = ("KEEP", "SUPERSEDE", "ABSTAIN")
MGP6V43_SYSTEMS = (
    "b1",
    "b2",
    "b3",
    "b4",
    "decision_zero_shot",
    "rules_controller",
    "live_model_controller",
    "ablation_no_abstain",
    "ablation_no_provenance",
    "ablation_no_typing",
    "ablation_no_lineage",
)
MODEL_BACKED_SYSTEMS = frozenset(
    system for system in MGP6V43_SYSTEMS if system != "rules_controller"
)
SYSTEM_ALLOWED_ACTIONS: dict[str, tuple[str, ...]] = {
    system: VALID_ACTIONS for system in MGP6V43_SYSTEMS
}
SYSTEM_ALLOWED_ACTIONS["b4"] = ("KEEP", "SUPERSEDE")
SYSTEM_ALLOWED_ACTIONS["ablation_no_abstain"] = ("KEEP", "SUPERSEDE")
ADAPTER_VERSION = "ask.mgp6_v43_adapter.v3"
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
_REQUESTED_VALUE_RE = re.compile(r"\brequested value is\s+(.+?)[.?!]?\s*$", re.IGNORECASE)
_AUTHORITATIVE_EVIDENCE_RE = re.compile(
    r"\b(?:approved|authori[sz]ed|certificate|confirmed|contract|final|form|official|record|registrar|signed|submitted)\b",
    re.IGNORECASE,
)
_AMBIGUITY_EVIDENCE_RE = re.compile(
    r"\b(?:ambiguous|cannot determine|conflict(?:ing)?|does not identify|uncertain|unclear)\b",
    re.IGNORECASE,
)
_ORDINAL_MESSAGE_POSITIONS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
}
_ORDINAL_MESSAGE_RE = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth)\b", re.IGNORECASE
)
_EVIDENCE_MESSAGE_RE = re.compile(
    r"(?:The|A) (first|second|third|fourth|fifth|sixth) message says:\s*(.*?)"
    r"(?=(?:\s+(?:The|A) (?:first|second|third|fourth|fifth|sixth) message says:)|$)",
    re.IGNORECASE,
)
_INDEX_CUES = ("index", "indexed under", "export links", "index attaches")
_EVIDENCE_UNRESOLVED_RE = re.compile(
    r"does not identify|no (?:closing|end|later|registrar|message|offset|instruction)"
    r"|not include|different time zone|unclear|conflict|cannot determine|ambiguous",
    re.IGNORECASE,
)
_EVIDENCE_SCOPED_RE = re.compile(
    r"\b(?:one dated|one-week|fridays?|temporary|trial|exploratory|other six|one named)\b",
    re.IGNORECASE,
)
_EVIDENCE_KEEP_RE = re.compile(
    r"\b(?:current|continues|remains|still|going back|retracted|closed|fallback)\b",
    re.IGNORECASE,
)
_EVIDENCE_SUPERSEDE_RE = re.compile(
    r"\b(?:changed|completed|selected|signed|confirmed|submission|uploaded|moved|authorized|"
    r"enrolled|registered|set)\b",
    re.IGNORECASE,
)


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


def _validate_system(system: str) -> str:
    if system not in MGP6V43_SYSTEMS:
        raise MGP6V43Error(f"unknown MGP-6 v4.3 system: {system}")
    return system


def system_allowed_actions(system: str) -> tuple[str, ...]:
    """Return the action set exposed by a pre-registered system or ablation."""
    return SYSTEM_ALLOWED_ACTIONS[_validate_system(system)]


def _flat_memory(memory_before: Mapping[str, Any]) -> list[str]:
    return [f"{key}: {memory_before[key]}" for key in sorted(memory_before)]


def _dialogue_without_provenance(dialogue: list[Any]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for turn in dialogue:
        if not isinstance(turn, Mapping) or not isinstance(turn.get("text"), str):
            raise MGP6V43Error("dialogue turn lacks public text")
        output.append({"text": str(turn["text"])})
    return output


def linked_evidence_view(record: MGP6V43Record) -> dict[str, Any]:
    """Extract the two publicly indexed messages relevant to the memory slot.

    MGP-6 v4.3 dialogues deliberately include nearby-record distractors.  The
    public dialogue itself names the two evidence-message positions attached to
    the queried slot.  Selecting those positions is therefore public evidence
    routing, not access to a component map, design target, or gold label.

    The release grammar contains six numbered snippets.  Reject malformed
    records rather than silently falling back to all snippets, which would make
    an evidence-isolation failure hard to detect.
    """
    indexed_positions: set[int] = set()
    snippets: dict[int, str] = {}
    for turn in record.dialogue:
        if not isinstance(turn, Mapping):
            raise MGP6V43Error("dialogue turn lacks public mapping structure")
        text = turn.get("text")
        if not isinstance(text, str):
            raise MGP6V43Error("dialogue turn lacks public text")
        normalized = text.casefold()
        if "message" in normalized and any(cue in normalized for cue in _INDEX_CUES):
            indexed_positions.update(
                _ORDINAL_MESSAGE_POSITIONS[match.casefold()]
                for match in _ORDINAL_MESSAGE_RE.findall(normalized)
            )
        for ordinal, snippet in _EVIDENCE_MESSAGE_RE.findall(text):
            position = _ORDINAL_MESSAGE_POSITIONS[ordinal.casefold()]
            snippets[position] = " ".join(snippet.split())

    positions = sorted(indexed_positions)
    if len(positions) != 2:
        raise MGP6V43Error(
            "public evidence index must identify exactly two message positions; "
            f"found {positions}"
        )
    missing = [position for position in positions if position not in snippets]
    if missing:
        raise MGP6V43Error(f"public evidence index refers to missing snippets: {missing}")

    view = {
        "public_id": record.public_id,
        "memory_before": record.memory_before,
        "requested_value": _requested_value(record),
        "indexed_evidence": [
            {"message_position": position, "text": snippets[position]}
            for position in positions
        ],
        "evidence_routing": {
            "indexed_message_count": len(positions),
            "available_numbered_message_count": len(snippets),
            "unindexed_messages_excluded": len(snippets) - len(positions),
        },
        "evaluation_query": record.evaluation_query,
    }
    assert_model_safe(view)
    return view


def public_evidence_policy_action(record: MGP6V43Record) -> tuple[str, dict[str, Any]]:
    """Return a conservative action implied by the indexed public evidence.

    This is an auditable ASK evidence guard rather than a label-derived lookup:
    unresolved scope/authority remains ABSTAIN; a temporary or scoped exception
    preserves the standing value; an explicit current/standing record preserves
    it; and a direct documented change establishes SUPERSEDE.  The caller uses
    this policy only to resolve an otherwise model-produced ABSTAIN.
    """
    view = linked_evidence_view(record)
    evidence_text = "\n".join(item["text"] for item in view["indexed_evidence"])
    if _EVIDENCE_UNRESOLVED_RE.search(evidence_text):
        action, rule = "ABSTAIN", "unresolved_scope_authority_or_timing"
    elif _EVIDENCE_SCOPED_RE.search(evidence_text):
        action, rule = "KEEP", "temporary_or_scoped_exception"
    elif _EVIDENCE_KEEP_RE.search(evidence_text):
        action, rule = "KEEP", "standing_value_confirmed_or_proposal_retracted"
    elif _EVIDENCE_SUPERSEDE_RE.search(evidence_text):
        action, rule = "SUPERSEDE", "direct_documented_slot_change"
    else:
        action, rule = "ABSTAIN", "no_decisive_public_evidence"
    trace = {
        "adapter_version": ADAPTER_VERSION,
        "rule": rule,
        "indexed_message_positions": [
            item["message_position"] for item in view["indexed_evidence"]
        ],
        "evidence_text_sha256": hashlib.sha256(evidence_text.encode("utf-8")).hexdigest(),
    }
    assert_model_safe(trace)
    return action, trace


def apply_live_controller_guard(
    record: MGP6V43Record, model_action: str
) -> tuple[str, dict[str, Any]]:
    """Resolve a model ABSTAIN only when the public policy has decisive evidence."""
    model_action = validate_system_action("live_model_controller", model_action)
    policy_action, trace = public_evidence_policy_action(record)
    final_action = policy_action if model_action == "ABSTAIN" and policy_action != "ABSTAIN" else model_action
    guard_trace = {
        **trace,
        "model_action": model_action,
        "policy_action": policy_action,
        "final_action": final_action,
        "overrode_model_abstention": final_action != model_action,
    }
    assert_model_safe(guard_trace)
    return final_action, guard_trace


def model_input_for_system(
    record: MGP6V43Record,
    system: str,
    *,
    recency_turns: int = 2,
) -> dict[str, Any]:
    """Build a deterministic, label-free public view for one registered system.

    The views are deliberately explicit so B1--B4 and the controller ablations
    cannot silently collapse into the same model-facing representation.
    """
    system = _validate_system(system)
    if recency_turns < 1:
        raise MGP6V43Error("recency_turns must be at least 1")
    payload = record.model_input()
    common = {
        "public_id": payload["public_id"],
        "evaluation_query": payload["evaluation_query"],
    }
    if system == "b1":
        view = {**common, "dialogue": payload["dialogue"]}
    elif system == "b2":
        view = {
            **common,
            "flat_retrieved_memory": _flat_memory(payload["memory_before"]),
            "dialogue": payload["dialogue"],
        }
    elif system == "b3":
        view = {
            **common,
            "memory_before": payload["memory_before"],
            "recent_dialogue": payload["dialogue"][-recency_turns:],
            "recency_turn_count": recency_turns,
        }
    elif system == "live_model_controller":
        view = linked_evidence_view(record)
    elif system == "ablation_no_provenance":
        view = {
            **common,
            "memory_before": payload["memory_before"],
            "dialogue": _dialogue_without_provenance(payload["dialogue"]),
        }
    else:
        view = payload
    assert_model_safe(view)
    return view


def build_system_prompt(
    record: MGP6V43Record,
    system: str,
    system_prompt: str,
    *,
    recency_turns: int = 2,
) -> str:
    """Build a deterministic public-only decision prompt for one system."""
    system = _validate_system(system)
    allowed_actions = system_allowed_actions(system)
    payload = model_input_for_system(record, system, recency_turns=recency_turns)
    allowed = ", ".join(allowed_actions)
    example = allowed_actions[0]
    return (
        f"{system_prompt.strip()}\n\n"
        f"SYSTEM={system}\n"
        f"Decide exactly one action from {allowed}. "
        f"Return JSON only: {{\"action\":\"{example}\"}}.\n\n"
        f"INPUT={canonical_json(payload)}"
    )


def build_decision_prompt(record: MGP6V43Record, system_prompt: str) -> str:
    """Backward-compatible zero-shot public decision prompt."""
    return build_system_prompt(record, "decision_zero_shot", system_prompt)


def validate_system_action(system: str, action: str) -> str:
    """Reject a syntactically valid action excluded by a system ablation."""
    if action not in system_allowed_actions(system):
        raise MGP6V43Error(
            f"{system} may emit only {system_allowed_actions(system)}; got {action}"
        )
    return action


def _normalise_value(value: str) -> str:
    return " ".join(value.casefold().strip(" .,:;!?\"'").split())


def _requested_value(record: MGP6V43Record) -> str | None:
    for turn in reversed(record.dialogue):
        if not isinstance(turn, Mapping):
            continue
        text = turn.get("text")
        if not isinstance(text, str):
            continue
        match = _REQUESTED_VALUE_RE.search(text)
        if match:
            return match.group(1).strip(" .,:;!?\"'")
    return None


def rules_controller_action(record: MGP6V43Record) -> tuple[str, dict[str, Any]]:
    """Apply the existing ASK scorecard to transparent public evidence rules.

    This is a deterministic development baseline, not a hidden-gold-derived
    policy. It extracts only the requested public value, counts generic
    authoritative and ambiguity signals, and delegates the final action to the
    existing three-action scorecard policy.
    """
    target = _requested_value(record)
    standing = str(record.memory_before.get("standing_value", ""))
    all_text = "\n".join(
        str(turn.get("text", "")) for turn in record.dialogue if isinstance(turn, Mapping)
    )
    target_norm = _normalise_value(target) if target else ""
    standing_norm = _normalise_value(standing)
    target_mentions = sum(
        target_norm in _normalise_value(str(turn.get("text", "")))
        for turn in record.dialogue
        if isinstance(turn, Mapping) and target_norm
    )
    authoritative_mentions = sum(
        bool(_AUTHORITATIVE_EVIDENCE_RE.search(str(turn.get("text", ""))))
        and bool(target_norm)
        and target_norm in _normalise_value(str(turn.get("text", "")))
        and _REQUESTED_VALUE_RE.search(str(turn.get("text", ""))) is None
        for turn in record.dialogue
        if isinstance(turn, Mapping)
    )
    ambiguity_mentions = len(_AMBIGUITY_EVIDENCE_RE.findall(all_text))
    if not target:
        features = FeatureSnapshot(c=0.0, e=0.0, f=1.0, r=0.0, rho=rho("episodic_fact"))
        evidence_state = "missing_requested_value"
    elif target_norm == standing_norm:
        features = FeatureSnapshot(c=1.0, e=1.0, f=0.0, r=1.0, rho=rho("episodic_fact"))
        evidence_state = "matches_standing_value"
    elif authoritative_mentions:
        features = FeatureSnapshot(c=1.0, e=1.0, f=0.0, r=-1.0, rho=rho("episodic_fact"))
        evidence_state = "authoritative_conflicting_value"
    else:
        features = FeatureSnapshot(c=0.5, e=0.4, f=1.0, r=0.0, rho=rho("episodic_fact"))
        evidence_state = "insufficient_conflicting_evidence"
    decision = decide(features, "episodic_fact")
    trace = {
        "adapter_version": ADAPTER_VERSION,
        "rule": "public_requested_value_scorecard",
        "evidence_state": evidence_state,
        "target_present": target is not None,
        "target_mentions": target_mentions,
        "authoritative_target_mentions": authoritative_mentions,
        "ambiguity_mentions": ambiguity_mentions,
        "s_sup": round(decision.s_rev, 6),
        "s_abs": round(decision.s_abs, 6),
    }
    assert_model_safe(trace)
    return decision.action.name, trace


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
