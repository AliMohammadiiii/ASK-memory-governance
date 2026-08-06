from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from mgp_natural.splitting.continuity import build_graph_file
from mgp_natural.splitting.split import build_splits
from mgp_natural.util.io import iter_jsonl, write_json, write_jsonl


def build(repo_root: Path) -> dict[str, Any]:
    private = repo_root / ".private" / "full"
    reports = repo_root / "reports"
    manifests = repo_root / "manifests"
    combined_manifest_rows: list[dict[str, Any]] = []
    track_reports: dict[str, Any] = {}
    for track in ("STUDYCHAT", "WIKICONV"):
        slug = track.casefold()
        items = private / f"{slug}_construction_items_redacted.jsonl"
        if not items.is_file():
            raise FileNotFoundError(f"missing full-source track items: {items}")
        if not any(True for _ in iter_jsonl(items)):
            raise ValueError(f"cannot split empty {track} candidate set")
        components = private / f"{slug}_components.jsonl"
        continuity_report = reports / f"{track}_CONTINUITY_FULL.json"
        split_manifest = private / f"{slug}_split_private.jsonl"
        split_report = reports / f"{track}_SPLIT_AUDIT_FULL.json"
        continuity = build_graph_file(items, components, continuity_report, 0.92)
        split = build_splits(items, components, split_manifest, split_report, seed=1729)
        rows = list(iter_jsonl(split_manifest))
        combined_manifest_rows.extend(rows)
        track_reports[track] = {"continuity": continuity, "split": split}
    combined_manifest_rows.sort(key=lambda row: (row["source_track"], row["item_id"]))
    write_jsonl(manifests / "splits_private.jsonl", combined_manifest_rows, mode=0o600)
    report = {
        "schema_version": "2.0",
        "seed": 1729,
        "tracks": track_reports,
        "tracks_kept_separate": True,
        "mixed_headline_score_created": False,
        "all_track_splits_valid": all(
            bool(track_reports[track]["split"]["split_audit_passed"])
            for track in track_reports
        ),
    }
    write_json(reports / "SPLIT_AUDIT_FULL.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build full-source continuity-safe splits")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(json.dumps(build(args.repo_root.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()

