from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from common import (
    absolute_source_path,
    find_file,
    load_json,
    system_from_card_id,
    utc_now,
    write_json,
)


REQUIRED_FIELDS = [
    "card_id",
    "concept_key",
    "status",
    "system_id",
    "work_id",
    "edition_ids",
    "evidence",
    "author_claim",
    "operationalization",
    "problem_solved",
    "required_inputs",
    "generation_questions",
    "diagnostic_criteria",
    "revision_methods",
    "applicable_when",
    "prohibited_when",
    "common_misuses",
    "cross_book_relations",
    "ai_short_adaptation",
    "user_notes",
    "external_supplements",
    "validation_records",
]


def validate_locator(locator: dict[str, Any], file_record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_type = file_record.get("locator_policy", {}).get("type")
    if locator.get("type") != expected_type:
        return [f"locator type {locator.get('type')} does not match {expected_type}"]
    if expected_type == "pdf_page":
        page = locator.get("pdf_page")
        page_count = file_record.get("inspection", {}).get("page_count")
        if not isinstance(page, int) or page < 1 or not isinstance(page_count, int) or page > page_count:
            errors.append(f"pdf_page {page} is outside 1..{page_count}")
        if locator.get("print_page") is not None and not isinstance(locator.get("print_page"), str):
            errors.append("print_page must be null or an explicit string")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(locator.get("text_hash", ""))):
            errors.append("PDF locator requires a sha256 text_hash")
    elif expected_type == "epub_anchor":
        chapter_href = locator.get("chapter_href")
        spine = file_record.get("inspection", {}).get("spine_hrefs", [])
        if chapter_href not in spine:
            errors.append(f"chapter_href does not exist in EPUB spine: {chapter_href}")
        if not isinstance(locator.get("paragraph_index"), int) or locator["paragraph_index"] < 1:
            errors.append("paragraph_index must be >= 1")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(locator.get("text_hash", ""))):
            errors.append("EPUB locator requires a sha256 text_hash")
    return errors


def validate_card(card: dict, registry: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in card:
            errors.append(f"Missing required field: {field}")

    if errors:
        return {"status": "fail", "errors": errors, "warnings": warnings}

    prefix = system_from_card_id(card["card_id"])
    if prefix is None:
        errors.append("Invalid card_id")
    elif prefix != card["system_id"]:
        errors.append("card_id prefix disagrees with system_id")
    if not str(card.get("concept_key", "")).strip():
        errors.append("concept_key cannot be empty")

    works = {item["work_id"]: item for item in registry.get("works", [])}
    editions = {item["edition_id"]: item for item in registry.get("editions", [])}
    work = works.get(card["work_id"])
    if not work:
        errors.append(f"Unknown work_id: {card['work_id']}")
    elif work["system_id"] != card["system_id"]:
        errors.append("work_id belongs to another theory system")
    for edition_id in card["edition_ids"]:
        edition = editions.get(edition_id)
        if not edition:
            errors.append(f"Unknown edition_id: {edition_id}")
        elif edition["work_id"] != card["work_id"]:
            errors.append(f"Edition {edition_id} belongs to another work")

    strong_evidence = False
    for index, evidence in enumerate(card["evidence"]):
        label = f"evidence[{index}]"
        try:
            file_record = find_file(registry, evidence.get("file_id", ""))
        except KeyError:
            errors.append(f"{label}: unknown file_id")
            continue
        if file_record["work_id"] != card["work_id"]:
            errors.append(f"{label}: cross-work source access blocked")
        if file_record["system_id"] != card["system_id"]:
            errors.append(f"{label}: cross-system source access blocked")
        if evidence.get("source_sha256") != file_record.get("sha256"):
            errors.append(f"{label}: source SHA-256 changed; card requires revalidation")
        status = evidence.get("evidence_status")
        if status in {"text_layer", "ocr_verified"}:
            strong_evidence = True
        errors.extend(f"{label}: {error}" for error in validate_locator(evidence.get("locator", {}), file_record))

    if card["status"] in {"reviewed", "approved"} and not strong_evidence:
        errors.append("Reviewed/approved card requires text_layer or ocr_verified book evidence")
    if card["status"] in {"reviewed", "approved"} and any(
        item.get("evidence_status") == "ocr_unverified" for item in card["evidence"]
    ):
        errors.append("Reviewed/approved card cannot rely on ocr_unverified evidence")

    adaptation = card.get("ai_short_adaptation", {})
    if adaptation.get("label") != "AI短片适配":
        errors.append("AI adaptation must retain the AI短片适配 label")

    for relation in card.get("cross_book_relations", []):
        if relation.get("governance") != "link_only":
            errors.append("Before G60 all cross-book relations must use governance=link_only")
        target = relation.get("target_card_id", "")
        if not system_from_card_id(target):
            errors.append(f"Invalid cross-book target_card_id: {target}")

    if not str(card.get("author_claim", "")).strip():
        errors.append("author_claim cannot be empty")
    if not str(card.get("operationalization", "")).strip():
        errors.append("operationalization cannot be empty")

    return {
        "checked_at": utc_now(),
        "card_id": card.get("card_id"),
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_card(load_json(args.card), load_json(args.registry))
    if args.report:
        write_json(args.report, report)
    print(f"Card validation: {report['status']}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
