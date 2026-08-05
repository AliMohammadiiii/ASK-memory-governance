from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.privacy.redaction import redact_jsonl
from mgp_natural.privacy.scanner import build_ner_detector, scan_jsonl


def _read_lexicon(path: Path | None) -> list[str]:
    if path is None:
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan privacy risks and optionally redact deterministically"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--findings", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--identity-lexicon", type=Path)
    parser.add_argument("--ner-backend", choices=["none", "spacy"], default="none")
    parser.add_argument("--ner-model")
    parser.add_argument("--redacted", type=Path)
    parser.add_argument("--redaction-log", type=Path)
    parser.add_argument("--redaction-summary", type=Path)
    args = parser.parse_args()
    lexicon = _read_lexicon(args.identity_lexicon)
    ner_detector = build_ner_detector(args.ner_backend, args.ner_model)
    print(
        scan_jsonl(
            args.input,
            args.findings,
            args.report,
            args.queue,
            lexicon,
            ner_detector=ner_detector,
        )
    )
    if args.redacted:
        if not args.redaction_log or not args.redaction_summary:
            parser.error("redaction outputs must be supplied together")
        print(
            redact_jsonl(
                args.input,
                args.redacted,
                args.redaction_log,
                args.redaction_summary,
                lexicon,
            )
        )


if __name__ == "__main__":
    main()

