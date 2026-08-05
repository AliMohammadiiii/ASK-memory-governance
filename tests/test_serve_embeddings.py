"""Security and resource-limit defaults for the local embedding server."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from serve_embeddings import build_parser  # type: ignore[import-not-found]  # noqa: E402


def test_embedding_server_defaults_to_loopback_without_remote_code() -> None:
    args = build_parser().parse_args([])

    assert args.host == "127.0.0.1"
    assert args.trust_remote_code is False
    assert args.max_request_bytes == 64 * 1024 * 1024


def test_embedding_server_risky_features_require_explicit_flags() -> None:
    args = build_parser().parse_args(["--host", "0.0.0.0", "--trust-remote-code"])

    assert args.host == "0.0.0.0"
    assert args.trust_remote_code is True


def test_embedding_server_rejects_nonpositive_body_limit() -> None:
    from serve_embeddings import main  # type: ignore[import-not-found]

    with pytest.raises(SystemExit, match="must be positive"):
        main(["--max-request-bytes", "0"])
