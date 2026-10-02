from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

from common import SYSTEM_IDS, load_json, sha256_file, utc_now, write_json


def duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def validate_registry(registry: dict, verify_hashes: bool = False) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    stale_file_ids: list[str] = []

    systems = {item.get("system_id"): item for item in registry.get("systems", [])}
    works = {item.get("work_id"): item for item in registry.get("works", [])}
    editions = {item.get("edition_id"): item for item in registry.get("editions", [])}
    files = registry.get("files", [])

    if set(systems) != SYSTEM_IDS:
        errors.append(f"System IDs must be exactly {sorted(SYSTEM_IDS)}; got={sorted(systems)}")
    if len(works) != 9:
        errors.append(f"Expected 9 distinct works; got={len(works)}")
    for work_id, work in works.items():
        if work.get("system_id") not in systems:
            errors.append(f"Work {work_id} references unknown system")
    for edition_id, edition in editions.items():
        if edition.get("work_id") not in works:
            errors.append(f"Edition {edition_id} references unknown work")

    for field in ("file_id", "relative_path", "sha256"):
        dupes = duplicates([str(item.get(field, "")) for item in files])
        if dupes:
            errors.append(f"Duplicate {field}: {dupes}")

    source_root = Path(registry.get("source_root", ""))
    for item in files:
        file_id = item.get("file_id", "<missing>")
        edition = editions.get(item.get("edition_id"))
        if not edition:
            errors.append(f"{file_id}: unknown edition_id")
            continue
        work = works[edition["work_id"]]
        if item.get("work_id") != work["work_id"]:
            errors.append(f"{file_id}: work_id disagrees with edition")
        if item.get("system_id") != work["system_id"]:
            errors.append(f"{file_id}: system_id disagrees with work")
        if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
            errors.append(f"{file_id}: invalid SHA-256")

        locator = item.get("locator_policy", {})
        suffix = item.get("format")
        if suffix == ".pdf" and locator.get("type") != "pdf_page":
            errors.append(f"{file_id}: PDF must use pdf_page locator")
        if suffix == ".epub" and locator.get("type") != "epub_anchor":
            errors.append(f"{file_id}: EPUB must use epub_anchor locator")

        path = source_root / Path(item["relative_path"])
        if not path.is_file():
            errors.append(f"{file_id}: source file missing: {path}")
        elif verify_hashes:
            actual_hash = sha256_file(path)
            if actual_hash != item["sha256"]:
                stale_file_ids.append(file_id)
                errors.append(f"{file_id}: SHA-256 changed; dependent outputs require revalidation")

    story_tw = [item for item in files if item.get("file_id") == "MCK-STORY-PDF-TW"]
    if len(story_tw) != 1 or story_tw[0].get("work_id") != "MCK-STORY":
        errors.append("繁体《故事的解剖》必须且只能归入 MCK-STORY")
    if any(item.get("work_id") == "TRU-ANATOMY" and "故事的解剖" in item.get("relative_path", "") for item in files):
        errors.append("McKee《故事的解剖》被错误归入 Truby")

    if registry.get("unmatched_files"):
        errors.append(f"Unmatched source files remain: {registry['unmatched_files']}")
    for edition_id in editions:
        if not any(item.get("edition_id") == edition_id for item in files):
            warnings.append(f"Edition has no file: {edition_id}")

    return {
        "checked_at": utc_now(),
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "stale_file_ids": stale_file_ids,
        "counts": {
            "systems": len(systems),
            "works": len(works),
            "editions": len(editions),
            "files": len(files),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verify-hashes", action="store_true")
    args = parser.parse_args()
    report = validate_registry(load_json(args.registry), args.verify_hashes)
    if args.report:
        write_json(args.report, report)
    print(f"Registry validation: {report['status']}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

