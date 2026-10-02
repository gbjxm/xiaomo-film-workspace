from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    CORE_EXTENSIONS,
    as_posix_relative,
    inspect_epub,
    inspect_pdf,
    load_json,
    locator_policy_for,
    resolve_single_glob,
    sha256_file,
    utc_now,
    write_json,
)


def inspect_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return inspect_pdf(path)
    if suffix == ".epub":
        return inspect_epub(path)
    return {"size_bytes": path.stat().st_size, "inspection": "hash_and_size_only"}


def build_registry(plan: dict) -> tuple[dict, dict]:
    root = Path(plan["source_root"])
    if not root.is_dir():
        raise FileNotFoundError(f"Source root does not exist: {root}")

    editions = {item["edition_id"]: item for item in plan["editions"]}
    works = {item["work_id"]: item for item in plan["works"]}
    systems = {item["system_id"]: item for item in plan["systems"]}

    resolved_paths: set[str] = set()
    file_records: list[dict] = []
    for spec in plan["files"]:
        path = resolve_single_glob(root, spec["path_glob"])
        suffix = path.suffix.lower()
        if suffix != spec["expected_format"].lower():
            raise ValueError(f"Format mismatch for {spec['file_id']}: {suffix}")
        relative_path = as_posix_relative(path, root)
        if relative_path in resolved_paths:
            raise ValueError(f"File mapped more than once: {relative_path}")
        resolved_paths.add(relative_path)

        edition = editions[spec["edition_id"]]
        work = works[edition["work_id"]]
        system = systems[work["system_id"]]
        file_records.append(
            {
                "file_id": spec["file_id"],
                "edition_id": edition["edition_id"],
                "work_id": work["work_id"],
                "system_id": system["system_id"],
                "relative_path": relative_path,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "format": suffix,
                "role": spec["role"],
                "ingestion": spec["ingestion"],
                "locator_policy": locator_policy_for(suffix, spec["ingestion"]),
                "inspection": inspect_file(path),
                "requires_revalidation": False,
            }
        )

    ignored_paths: dict[str, str] = {}
    for ignored in plan.get("ignored_files", []):
        for path in root.glob(ignored["path_glob"]):
            if path.is_file():
                ignored_paths[as_posix_relative(path, root)] = ignored["reason"]

    all_candidate_paths = {
        as_posix_relative(path, root)
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in CORE_EXTENSIONS
    }
    unmatched = sorted(all_candidate_paths - resolved_paths - set(ignored_paths))

    registry = {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "source_root": str(root.resolve()),
        "systems": plan["systems"],
        "works": plan["works"],
        "editions": plan["editions"],
        "files": sorted(file_records, key=lambda item: item["file_id"]),
        "ignored_files": [
            {"relative_path": path, "reason": reason}
            for path, reason in sorted(ignored_paths.items())
        ],
        "unmatched_files": unmatched,
    }
    report = {
        "generated_at": registry["generated_at"],
        "system_count": len(registry["systems"]),
        "work_count": len(registry["works"]),
        "edition_count": len(registry["editions"]),
        "file_count": len(registry["files"]),
        "ignored_file_count": len(registry["ignored_files"]),
        "unmatched_file_count": len(unmatched),
        "unmatched_files": unmatched,
        "status": "pass" if not unmatched else "fail",
    }
    return registry, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    registry, report = build_registry(load_json(args.plan))
    write_json(args.output, registry)
    write_json(args.report, report)
    print(f"Registered {report['file_count']} files across {report['work_count']} works.")
    if report["status"] != "pass":
        print(f"Unmatched source files: {report['unmatched_files']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

