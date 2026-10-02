from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import utc_now, write_json

EXCLUDED_PARTS = {".venv-ocr", "__pycache__"}


def included(path: Path, root: Path) -> bool:
    return not any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts)


def validate(root: Path) -> dict:
    errors: list[str] = []
    json_count = 0
    jsonl_count = 0
    jsonl_rows = 0
    for path in sorted(path for path in root.rglob("*.json") if included(path, root)):
        json_count += 1
        try:
            with path.open("r", encoding="utf-8") as handle:
                json.load(handle)
        except Exception as exc:
            errors.append(f"{path}: {type(exc).__name__}: {exc}")
    for path in sorted(path for path in root.rglob("*.jsonl") if included(path, root)):
        jsonl_count += 1
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    json.loads(line)
                    jsonl_rows += 1
        except Exception as exc:
            errors.append(f"{path}:{line_number}: {type(exc).__name__}: {exc}")
    return {
        "checked_at": utc_now(),
        "status": "pass" if not errors else "fail",
        "json_files": json_count,
        "jsonl_files": jsonl_count,
        "jsonl_rows": jsonl_rows,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate(args.root)
    if args.report:
        write_json(args.report, report)
    print(
        f"JSON artifact validation: {report['status']} "
        f"({report['json_files']} JSON, {report['jsonl_files']} JSONL, "
        f"{report['jsonl_rows']} JSONL rows)"
    )
    for error in report["errors"]:
        print(f"ERROR: {error}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
