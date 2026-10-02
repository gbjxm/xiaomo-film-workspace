from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    absolute_source_path,
    find_file,
    load_json,
    safe_output_path,
    short_text_hash,
)


def parse_page_spec(spec: str | None, page_count: int) -> list[int]:
    if not spec:
        return list(range(1, page_count + 1))
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    invalid = sorted(page for page in pages if page < 1 or page > page_count)
    if invalid:
        raise ValueError(f"PDF page out of range: {invalid}")
    return sorted(pages)


def extract_pdf(
    registry_path: Path,
    file_id: str,
    output_path: Path,
    allowed_output_root: Path,
    expected_work_id: str | None = None,
    page_spec: str | None = None,
) -> dict:
    import fitz

    registry = load_json(registry_path)
    record = find_file(registry, file_id)
    if record["format"] != ".pdf":
        raise ValueError(f"{file_id} is not a PDF")
    if expected_work_id and record["work_id"] != expected_work_id:
        raise ValueError(
            f"Cross-work access blocked: requested {expected_work_id}, file belongs to {record['work_id']}"
        )
    if record["ingestion"] == "ocr_required":
        raise ValueError(f"{file_id} requires OCR; text-layer extraction is forbidden")

    source_path = absolute_source_path(registry, record)
    output_path = safe_output_path(output_path, allowed_output_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(source_path)
    pages = parse_page_spec(page_spec, doc.page_count)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for pdf_page in pages:
            page = doc[pdf_page - 1]
            blocks = []
            for block in page.get_text("blocks", sort=True):
                text = str(block[4]).strip()
                if not text:
                    continue
                blocks.append(
                    {
                        "bbox": [round(float(value), 2) for value in block[:4]],
                        "text": text,
                        "text_hash": short_text_hash(text),
                    }
                )
            page_text = "\n".join(block["text"] for block in blocks)
            row = {
                "file_id": file_id,
                "source_sha256": record["sha256"],
                "work_id": record["work_id"],
                "edition_id": record["edition_id"],
                "locator": {
                    "type": "pdf_page",
                    "pdf_page": pdf_page,
                    "print_page": None,
                    "text_hash": short_text_hash(page_text),
                },
                "evidence_status": "text_layer",
                "blocks": blocks,
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    doc.close()
    return {"file_id": file_id, "pages_written": len(pages), "output": str(output_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--file-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allowed-output-root", type=Path, required=True)
    parser.add_argument("--expected-work-id")
    parser.add_argument("--pages")
    args = parser.parse_args()
    result = extract_pdf(
        args.registry,
        args.file_id,
        args.output,
        args.allowed_output_root,
        args.expected_work_id,
        args.pages,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
