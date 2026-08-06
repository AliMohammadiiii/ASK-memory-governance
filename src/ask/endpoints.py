"""Validation for configurable HTTP endpoints and server bind addresses."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

_HOSTNAME_RE = re.compile(
    r"(?=.{1,253}\Z)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z"
)


def is_loopback_host(host: str) -> bool:
    """Return whether *host* is a literal loopback address or ``localhost``."""
    candidate = host.strip().strip("[]").lower()
    if candidate == "localhost":
        return True
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


def validate_http_endpoint(
    value: str,
    *,
    allow_insecure_http: bool = False,
) -> str:
    """Validate an HTTP(S) base endpoint without changing the supplied value.

    HTTPS is accepted for remote hosts. Plain HTTP is accepted for loopback
    hosts, or for other hosts only when ``allow_insecure_http`` is explicit.
    """
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("endpoint must be a non-empty URL without surrounding whitespace")
    if any(character.isspace() for character in value):
        raise ValueError("endpoint must not contain whitespace")

    parsed = urlsplit(value)
    if not parsed.scheme:
        raise ValueError("endpoint must include an explicit http or https scheme")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"unsupported endpoint scheme {parsed.scheme!r}; use http or https")
    if not parsed.netloc or parsed.hostname is None:
        raise ValueError("endpoint must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("endpoint must not contain embedded credentials")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"endpoint has an invalid port: {exc}") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("endpoint port must be between 1 and 65535")
    if parsed.scheme == "http" and not (is_loopback_host(parsed.hostname) or allow_insecure_http):
        raise ValueError(
            "plain HTTP is restricted to loopback hosts; set allow_insecure_http=True "
            "for a controlled remote endpoint"
        )
    return value


def validate_bind_address(
    host: str,
    port: int,
    *,
    allow_non_loopback: bool = False,
) -> tuple[str, int]:
    """Validate a server bind target and require opt-in outside loopback."""
    if not isinstance(host, str) or not host or host != host.strip():
        raise ValueError("bind host must be non-empty and contain no surrounding whitespace")
    if "://" in host or any(character.isspace() for character in host):
        raise ValueError("bind host must be a host or IP address, not a URL")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("bind port must be an integer between 1 and 65535")

    candidate = host.strip("[]")
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        if _HOSTNAME_RE.fullmatch(candidate) is None:
            raise ValueError(f"invalid bind host {host!r}") from None

    if not is_loopback_host(candidate) and not allow_non_loopback:
        raise ValueError("non-loopback binding requires explicit allow_non_loopback=True opt-in")
    return host, port
