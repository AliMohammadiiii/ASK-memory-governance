"""Official-source metadata and resumable WikiConv acquisition."""
from __future__ import annotations

import socket
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mgp_natural.errors import SourceChangedError, ValidationError
from mgp_natural.util.io import sha256_file, write_json

OFFICIAL_REPOSITORY = "https://github.com/conversationai/wikidetox/tree/main/wikiconv"
OFFICIAL_PAPER = "https://arxiv.org/abs/1810.13181"
CONVOKIT_DOCS = "https://convokit.cornell.edu/documentation/wikiconv.html"


@dataclass(frozen=True)
class DownloadSpec:
    identifier: str
    url: str
    filename: str
    expected_sha256: str | None = None
    expected_bytes: int | None = None
    source_version: str = "2018-07-01"


def resumable_download(spec: DownloadSpec, destination: Path, timeout: int = 60) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    final = destination / spec.filename
    partial = destination / f"{spec.filename}.part"
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": "mgp-natural/0.1 (+research acquisition audit)"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(spec.url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if offset and status != 206:
                partial.unlink(missing_ok=True)
                offset = 0
                return resumable_download(spec, destination, timeout=timeout)
            mode = "ab" if offset else "wb"
            with partial.open(mode) as handle:
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
    except urllib.error.URLError as exc:
        raise ValidationError(f"download failed for {spec.identifier}: {exc.reason}") from exc
    partial.replace(final)
    observed_hash = sha256_file(final)
    observed_bytes = final.stat().st_size
    if spec.expected_sha256 and observed_hash != spec.expected_sha256:
        raise SourceChangedError(
            f"hash changed for {spec.identifier}: expected {spec.expected_sha256}, got {observed_hash}"
        )
    if spec.expected_bytes is not None and observed_bytes != spec.expected_bytes:
        raise SourceChangedError(
            f"size changed for {spec.identifier}: expected {spec.expected_bytes}, got {observed_bytes}"
        )
    metadata = {
        "spec": asdict(spec),
        "observed_sha256": observed_hash,
        "observed_bytes": observed_bytes,
        "downloaded_at_unix": int(time.time()),
    }
    write_json(destination / f"{spec.filename}.source.json", metadata)
    return metadata



def runtime_acquisition_attempt(access_date: str) -> dict[str, Any]:
    hosts = ("raw.githubusercontent.com", "github.com", "convokit.cornell.edu")
    checks: list[dict[str, Any]] = []
    for host in hosts:
        try:
            addresses = {
                entry[4][0]
                for entry in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            }
            checks.append(
                {"host": host, "dns_status": "RESOLVED", "address_count": len(addresses)}
            )
        except OSError as exc:
            checks.append(
                {
                    "host": host,
                    "dns_status": "FAILED",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    all_resolved = all(check["dns_status"] == "RESOLVED" for check in checks)
    status = (
        "NETWORK_RESOLVED_SOURCE_SPEC_STILL_REQUIRED"
        if all_resolved
        else "BLOCKED_RUNTIME_NETWORK_RESOLUTION"
    )
    return {
        "schema_version": "1.0",
        "access_date": access_date,
        "status": status,
        "natural_artifact_acquired": False,
        "official_small_fixture_identified": True,
        "identified_fixture_evidence": {
            "repository": OFFICIAL_REPOSITORY,
            "description": (
                "Official repository contains bounded natural reconstruction test data; "
                "exact bytes must be acquired and hashed before use."
            ),
            "hash_status": "UNAVAILABLE_BECAUSE_BYTES_NOT_MATERIALIZED",
        },
        "runtime_dns_checks": checks,
        "manual_transcription_performed": False,
        "synthetic_fixture_only": True,
        "next_authorized_action": (
            "Run scripts/acquire_wikiconv.py with a pinned official DownloadSpec in a "
            "network-enabled environment, then hash and audit the exact bytes."
        ),
        "claim_boundary": (
            "No natural WikiConv candidate count, split, privacy result, or benchmark-readiness "
            "claim is supported by this execution."
        ),
    }


def write_runtime_acquisition_attempt(output: Path, access_date: str) -> dict[str, Any]:
    report = runtime_acquisition_attempt(access_date)
    write_json(output, report)
    return report

def official_source_manifest(access_date: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "access_date": access_date,
        "dataset": "WikiConv",
        "source_version": "2018-07-01 Wikipedia dumps",
        "official_repository": OFFICIAL_REPOSITORY,
        "official_paper": OFFICIAL_PAPER,
        "official_tooling_docs": CONVOKIT_DOCS,
        "dataset_wrapper_license_evidence": "CC0-1.0 stated by official repository",
        "underlying_comment_text_license_evidence": "CC-BY-SA-3.0 stated by official repository",
        "legal_status": "HUMAN_LEGAL_REVIEW_REQUIRED",
        "real_acquisition_status": "NOT_ACQUIRED_IN_THIS_EXECUTION",
        "runtime_acquisition_blocker": "BLOCKED_RUNTIME_NETWORK_RESOLUTION",
        "official_small_fixture_identified": True,
        "acquisition_attempt_report": "reports/WIKICONV_ACQUISITION_ATTEMPT.json",
        "reason": (
            "Official source and small natural test-fixture evidence were identified, but the code "
            "runtime could not resolve the official hosts and no source bytes were materialized. "
            "Synthetic fixtures exercise the interface only."
        ),
    }


def write_official_source_manifest(output: Path, access_date: str) -> None:
    write_json(output, official_source_manifest(access_date))

