from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from common import load_json, utc_now, write_json


ALLOWED_STATUSES = {
    "pending",
    "mapped",
    "carded",
    "excluded_with_reason",
    "unreadable",
}


def validate_chapter_map(chapter_map: dict, registry: dict) -> dict:
    errors: list[str] = []
    works = {item["work_id"]: item for item in registry.get("works", [])}
    editions = {item["edition_id"]: item for item in registry.get("editions", [])}
    work_id = chapter_map.get("work_id")
    if work_id not in works:
        errors.append(f"Unknown work_id: {work_id}")
    if chapter_map.get("coverage_mode") != "complete_map_selective_cards":
        errors.append("coverage_mode must be complete_map_selective_cards")
    for edition_id in chapter_map.get("edition_ids", []):
        edition = editions.get(edition_id)
        if not edition:
            errors.append(f"Unknown edition_id: {edition_id}")
        elif edition.get("work_id") != work_id:
            errors.append(f"Edition belongs to another work: {edition_id}")

    sections = chapter_map.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections must be a non-empty list")
        sections = []
    required = {
        "section_id",
        "title",
        "source_range",
        "processing_status",
        "main_topic",
        "argument_progression",
        "examples",
        "actionability",
        "exclusion_reason",
    }
    for index, section in enumerate(sections):
        missing = sorted(required - set(section))
        if missing:
            errors.append(f"sections[{index}] missing fields: {missing}")
        status = section.get("processing_status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"sections[{index}] invalid processing_status: {status}")
        if status == "excluded_with_reason" and not str(section.get("exclusion_reason", "")).strip():
            errors.append(f"sections[{index}] excluded section requires a reason")
        if status != "excluded_with_reason" and section.get("exclusion_reason"):
            errors.append(f"sections[{index}] exclusion_reason is only valid for excluded sections")
    counts = Counter(section.get("section_id") for section in sections)
    for section_id, count in counts.items():
        if count > 1:
            errors.append(f"Duplicate section_id: {section_id}")

    return {
        "checked_at": utc_now(),
        "status": "pass" if not errors else "fail",
        "section_count": len(sections),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--chapter-map", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_chapter_map(load_json(args.chapter_map), load_json(args.registry))
    if args.report:
        write_json(args.report, report)
    print(f"Chapter map validation: {report['status']}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
