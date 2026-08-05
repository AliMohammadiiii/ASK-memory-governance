"""StudyChat archive auditing and authorized local ingestion."""
from __future__ import annotations

import json
import os
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from mgp_natural.errors import SourceChangedError, ValidationError
from mgp_natural.util.io import iter_jsonl, sha256_file, write_json

EXPECTED_SAMPLE_FILES = {
    "stats.json",
    "mgp_candidate_sample.jsonl",
    "long_chat_sample.jsonl",
}


def safe_extract_zip(archive: Path, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    os.chmod(destination, 0o700)
    destination = destination.resolve()
    resolved_root = destination
    extracted: list[Path] = []
    try:
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                target = (destination / info.filename).resolve()
                if target != resolved_root and resolved_root not in target.parents:
                    raise ValidationError(f"unsafe archive member: {info.filename}")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    os.chmod(target, 0o700)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                current = target.parent
                while current == resolved_root or resolved_root in current.parents:
                    os.chmod(current, 0o700)
                    if current == resolved_root:
                        break
                    current = current.parent
                with bundle.open(info) as source, target.open("wb") as sink:
                    while chunk := source.read(1024 * 1024):
                        sink.write(chunk)
                os.chmod(target, 0o600)
                extracted.append(target)
    except zipfile.BadZipFile as exc:
        raise ValidationError(f"malformed ZIP: {archive}") from exc
    return extracted


def _count_jsonl(path: Path) -> tuple[int, set[str]]:
    count = 0
    keys: set[str] = set()
    for row in iter_jsonl(path):
        count += 1
        keys.update(row)
    return count, keys


def audit_archive(archive: Path, destination: Path) -> dict[str, Any]:
    destination = destination.resolve()
    extracted = safe_extract_zip(archive, destination)
    files = []
    by_name = {path.name: path for path in extracted}
    for path in sorted(extracted):
        entry: dict[str, Any] = {
            "path": path.relative_to(destination).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        if path.suffix == ".jsonl":
            entry["records"], entry["observed_keys"] = _count_jsonl(path)
            entry["observed_keys"] = sorted(entry["observed_keys"])
        elif path.name == "stats.json":
            entry["object"] = json.loads(path.read_text(encoding="utf-8"))
        files.append(entry)
    names = set(by_name)
    classification = "UNKNOWN_DERIVATIVE"
    reasons = []
    if EXPECTED_SAMPLE_FILES.issubset(names):
        candidate_count, _ = _count_jsonl(by_name["mgp_candidate_sample.jsonl"])
        long_count, _ = _count_jsonl(by_name["long_chat_sample.jsonl"])
        if candidate_count == 1000 and long_count == 100:
            classification = "SAMPLE_DERIVATIVE"
            reasons.append("observed 1,000 candidate rows and 100 long-chat rows")
    return {
        "schema_version": "1.0",
        "archive": {
            "path": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": sha256_file(archive),
        },
        "files": files,
        "classification": classification,
        "classification_reasons": reasons,
    }


def verify_archive_hash(archive: Path, expected_sha256: str) -> None:
    observed = sha256_file(archive)
    if observed != expected_sha256:
        raise SourceChangedError(f"archive hash mismatch: expected {expected_sha256}, got {observed}")


def locate_derivative(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_file() and path.name in EXPECTED_SAMPLE_FILES:
            found[path.name] = path
    missing = EXPECTED_SAMPLE_FILES - set(found)
    if missing:
        raise ValidationError(f"missing derivative files: {sorted(missing)}")
    return found


def summarize_derivative(root: Path) -> dict[str, Any]:
    paths = locate_derivative(root)
    candidates = list(iter_jsonl(paths["mgp_candidate_sample.jsonl"]))
    long_chats = list(iter_jsonl(paths["long_chat_sample.jsonl"]))
    nested = sum(len(row.get("interactions", [])) for row in long_chats)
    return {
        "classification": "SAMPLE_DERIVATIVE",
        "candidate_rows": len(candidates),
        "candidate_users": len({row["user_id_hash"] for row in candidates}),
        "candidate_chats": len({row["chat_id_hash"] for row in candidates}),
        "candidate_semesters": dict(Counter(row["semester"] for row in candidates)),
        "long_chat_rows": len(long_chats),
        "long_chat_interactions": nested,
        "long_chat_users": len({row["user_id_hash"] for row in long_chats}),
        "long_chat_chats": len({row["chat_id_hash"] for row in long_chats}),
    }


def acquire_authorized_huggingface(
    output_dir: Path,
    repo_id: str = "wmcnicho/StudyChat",
    revision: str | None = None,
    local_files_only: bool = False,
) -> Path:
    """Download only after a human has separately accepted any gated terms.

    This function never attempts to accept terms. A token may be read by the
    Hugging Face client from its standard environment/cache, but is never
    printed or persisted by this project.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise ValidationError(
            "install the optional 'huggingface' extra to use authorized acquisition"
        ) from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    token_present = bool(os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN"))
    try:
        path = snapshot_download(
            repo_id=repo_id,
            revision=revision,
            local_dir=output_dir,
            local_files_only=local_files_only,
            token=True if token_present else None,
        )
    except Exception as exc:  # client exception classes vary by version
        raise ValidationError(
            "StudyChat acquisition unavailable. An authorized human must accept any gated "
            "terms and provide credentials or an authorized local cache."
        ) from exc
    return Path(path)


def write_audit_report(archive: Path, destination: Path, output: Path) -> None:
    write_json(output, audit_archive(archive, destination))

