from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from common import utc_now, write_json


def files_modified_since(root: Path, since: datetime) -> list[dict]:
    changed = []
    if not root.exists():
        return changed
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=since.tzinfo)
        if modified >= since:
            changed.append({"path": str(path.resolve()), "modified_at": modified.isoformat()})
    return changed


def formal_outputs(root: Path) -> list[str]:
    results = []
    for relative in ("知识卡", "章节地图"):
        target = root / relative
        if target.exists():
            results.extend(str(path.resolve()) for path in target.rglob("*") if path.is_file())
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--g01-start", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--skill-root", type=Path, required=True)
    parser.add_argument("--engineering-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    since = datetime.fromisoformat(args.g01_start)
    source_changes = files_modified_since(args.source_root, since)
    skill_changes = files_modified_since(args.skill_root, since)
    outputs = formal_outputs(args.engineering_root)
    errors = []
    if source_changes:
        errors.append("Original source files were modified after G01 started")
    if skill_changes:
        errors.append("develop-screenplay-from-idea Skill was modified after G01 started")
    if outputs:
        errors.append("Formal knowledge cards or chapter maps exist during G01")
    report = {
        "checked_at": utc_now(),
        "g01_start": since.isoformat(),
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "source_files_modified_since_start": source_changes,
        "skill_files_modified_since_start": skill_changes,
        "formal_knowledge_outputs": outputs,
    }
    write_json(args.report, report)
    print(
        f"G01 boundary audit: {report['status']}; "
        f"source_changes={len(source_changes)}, skill_changes={len(skill_changes)}, "
        f"formal_outputs={len(outputs)}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
