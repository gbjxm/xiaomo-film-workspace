from __future__ import annotations

import argparse
from pathlib import Path

from common import load_json, utc_now, write_json


EXPECTED_FILES = {"STC01-PDF-01", "STC02-PDF-01", "STC03-PDF-01", "EGR-PDF-01"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-plan", type=Path, required=True)
    parser.add_argument("--rapid-full", type=Path, required=True)
    parser.add_argument("--rapid-cer", type=Path, required=True)
    parser.add_argument("--paddle-cer", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--paddle-timeout", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    plan = load_json(args.sample_plan)
    books = plan.get("books", [])
    if {book.get("file_id") for book in books} != EXPECTED_FILES:
        errors.append("OCR sample plan does not contain exactly the four scanned books")
    for book in books:
        if len(book.get("samples", [])) != 12:
            errors.append(f"{book.get('file_id')}: expected 12 samples")
        if not book.get("source_sha256"):
            errors.append(f"{book.get('file_id')}: missing source_sha256")
        for sample in book.get("samples", []):
            if not Path(sample.get("image_path", "")).is_file():
                errors.append(f"Missing sample image: {sample.get('image_path')}")
        target = book.get("cer_target", {})
        if not Path(target.get("image_path", "")).is_file():
            errors.append(f"{book.get('file_id')}: missing CER crop")

    rapid_full = load_json(args.rapid_full)
    full_rows = [row for row in rapid_full.get("results", []) if row.get("kind") == "full_page"]
    if len(full_rows) != 48 or any(row.get("error") for row in full_rows):
        errors.append("RapidOCR must have 48 successful full-page results")
    if any(not row.get("source_sha256") for row in full_rows):
        errors.append("RapidOCR full-page results are missing source hashes")

    for label, path in (("RapidOCR", args.rapid_cer), ("PaddleOCR", args.paddle_cer)):
        report = load_json(path)
        rows = [row for row in report.get("results", []) if row.get("kind") == "cer_crop"]
        if len(rows) != 4 or any(row.get("error") for row in rows):
            errors.append(f"{label} must have four successful CER crop results")

    truth = load_json(args.ground_truth)
    if len(truth.get("targets", [])) != 4:
        errors.append("Ground truth must contain four manually transcribed targets")
    comparison = load_json(args.comparison)
    summaries = comparison.get("summary", {})
    if set(summaries) != {"rapidocr", "paddleocr"}:
        errors.append("CER comparison must include both engines")
    timeout = load_json(args.paddle_timeout)
    if timeout.get("outcome") != "stopped_after_exceeding_throughput_limit":
        errors.append("Paddle full-page throughput outcome is not recorded")

    report = {
        "checked_at": utc_now(),
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "counts": {
            "books": len(books),
            "sample_pages": sum(len(book.get("samples", [])) for book in books),
            "rapid_full_pages": len(full_rows),
            "ground_truth_targets": len(truth.get("targets", [])),
        },
        "cer_summary": summaries,
    }
    write_json(args.report, report)
    print(f"OCR evidence validation: {report['status']}")
    for error in errors:
        print(f"ERROR: {error}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
