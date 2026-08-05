"""Text canonicalization and similarity helpers."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"[A-Za-z0-9_]+")


def canonicalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    return _WS.sub(" ", normalized)


def tokens(value: str) -> list[str]:
    return _TOKEN.findall(canonicalize_text(value))


def token_jaccard(left: str, right: str) -> float:
    a, b = set(tokens(left)), set(tokens(right))
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def multiset_f1(left: list[str], right: list[str]) -> float:
    a, b = Counter(left), Counter(right)
    overlap = sum((a & b).values())
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    precision = overlap / len(left)
    recall = overlap / len(right)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)

