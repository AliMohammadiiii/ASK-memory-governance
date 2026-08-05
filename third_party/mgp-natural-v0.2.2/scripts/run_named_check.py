from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from mgp_natural.util.io import write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a named development check with a report")
    parser.add_argument("--name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a command is required after --")
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    report = {
        "schema_version": "1.0",
        "name": args.name,
        "command": command,
        "returncode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "output_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
        "output_tail": completed.stdout[-8000:],
    }
    write_json(args.output, report)
    print(completed.stdout, end="")
    print(json.dumps({key: report[key] for key in ("name", "status", "returncode")}))
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()

