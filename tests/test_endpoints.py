from __future__ import annotations

import pytest

from ask.endpoints import validate_bind_address, validate_http_endpoint


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.test/v1",
        "http://localhost:8100/v1",
        "http://127.0.0.1:8100/v1",
        "http://[::1]:8100/v1",
    ],
)
def test_valid_endpoints_are_preserved(endpoint: str) -> None:
    assert validate_http_endpoint(endpoint) == endpoint


@pytest.mark.parametrize(
    ("endpoint", "message"),
    [
        ("example.test/v1", "explicit"),
        ("ftp://example.test/v1", "unsupported"),
        ("https:///v1", "host"),
        ("https://user:secret@example.test/v1", "credentials"),
        ("https://example.test:70000/v1", "port"),
        ("https://example.test:not-a-port/v1", "port"),
    ],
)
def test_invalid_endpoints_are_rejected(endpoint: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_http_endpoint(endpoint)


def test_remote_plain_http_requires_explicit_opt_in() -> None:
    endpoint = "http://192.0.2.10:8100/v1"

    with pytest.raises(ValueError, match="loopback"):
        validate_http_endpoint(endpoint)

    assert validate_http_endpoint(endpoint, allow_insecure_http=True) == endpoint


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "127.0.0.2", "::1"])
def test_loopback_bind_targets_are_allowed(host: str) -> None:
    assert validate_bind_address(host, 8100) == (host, 8100)


def test_non_loopback_bind_requires_explicit_opt_in() -> None:
    with pytest.raises(ValueError, match="explicit"):
        validate_bind_address("0.0.0.0", 8100)

    assert validate_bind_address("0.0.0.0", 8100, allow_non_loopback=True) == (
        "0.0.0.0",
        8100,
    )


@pytest.mark.parametrize("port", [0, 65536, -1, True])
def test_invalid_bind_ports_are_rejected(port: int) -> None:
    with pytest.raises(ValueError, match="port"):
        validate_bind_address("127.0.0.1", port)


@pytest.mark.parametrize("host", ["", "not a host", "http://localhost"])
def test_invalid_bind_hosts_are_rejected(host: str) -> None:
    with pytest.raises(ValueError, match="host"):
        validate_bind_address(host, 8100)
