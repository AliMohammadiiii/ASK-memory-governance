#!/usr/bin/env python3
"""Run a frozen extraction prompt over a JSONL turn set."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.extraction import Extractor  # noqa: E402
from ask.inference.llm import StructuredLLM  # noqa: E402
from ask.inference.ollama import OllamaLLM  # noqa: E402


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--prompt", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--trace", type=Path, default=None)
    p.add_argument("--ollama-model", default="gemma4:e4b")
    p.add_argument("--ollama-host", default="http://localhost:11434")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-new-tokens", type=int, default=512)
    p.add_argument("--num-ctx", type=int, default=8192)
    p.add_argument(
        "--json-format",
        action="store_true",
        help="Ask Ollama to constrain the response to a JSON object.",
    )
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.trace is not None:
        args.trace.parent.mkdir(parents=True, exist_ok=True)
        args.trace.write_text("", encoding="utf-8")

    llm = StructuredLLM(
        OllamaLLM(
            model_id=args.ollama_model,
            host=args.ollama_host,
            num_ctx=args.num_ctx,
            response_format="json" if args.json_format else None,
        )
    )
    extractor = Extractor.from_template_file(llm, args.prompt, log_path=args.trace)

    rows = list(_iter_jsonl(args.input))
    if args.limit is not None:
        rows = rows[: args.limit]

    with args.out.open("w", encoding="utf-8") as fh:
        for i, row in enumerate(rows, start=1):
            window = row.get("surrounding_window") or [None, None]
            output = extractor.extract(
                row,
                (window[0], window[1]),
                max_new_tokens=args.max_new_tokens,
                temperature=args.temperature,
                seed=args.seed,
            )
            record = {
                "turn_id": row["turn_id"],
                "session_id": row["session_id"],
                "turn_idx": row["turn_idx"],
                "source_role": row["role"],
                "model_id": args.ollama_model,
                "temperature": args.temperature,
                "seed": args.seed,
                "prompt": str(args.prompt),
                "output": output.model_dump(),
            }
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
            print(f"[{i}/{len(rows)}] {row['turn_id']} items={len(output.items)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
