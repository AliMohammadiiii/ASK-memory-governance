from __future__ import annotations

from scripts.reproduction.run_clean_reproduction import ROOT, _sanitize_text, _sanitize_value


def test_clean_reproduction_receipt_removes_local_paths_and_checkout_identity() -> None:
    raw = (
        "/local/example/repository/schema.json "
        "/private/var/folders/aa/bb/T/ask-repro-example/venv/bin/python "
        "/var/folders/aa/bb/T/pip-ephem-wheel-cache-example/wheel "
        "-e git+ssh://git@github.com/example/private.git@abc#egg=ask_memory_governance"
    ).replace("/local/example/repository", str(ROOT))

    sanitized = _sanitize_text(raw)

    assert str(ROOT) not in sanitized
    assert "/var/folders/" not in sanitized
    assert "/private/var/folders/" not in sanitized
    assert "github.com/example/private" not in sanitized
    assert "$REPO/schema.json" in sanitized
    assert "$REPRO_TMP/venv/bin/python" in sanitized
    assert "$PIP_EPHEMERAL_CACHE/wheel" in sanitized
    assert "$REPRO_SOURCE#egg=ask_memory_governance" in sanitized


def test_clean_reproduction_receipt_sanitizes_nested_values() -> None:
    value = {"commands": [["PYTHON=/var/folders/aa/bb/T/ask-repro-run/venv/bin/python"]]}

    assert _sanitize_value(value) == {"commands": [["PYTHON=$REPRO_TMP/venv/bin/python"]]}
