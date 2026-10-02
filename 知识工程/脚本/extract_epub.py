from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from lxml import html

from common import (
    absolute_source_path,
    find_file,
    load_json,
    safe_output_path,
    short_text_hash,
)


def epub_spine(archive: zipfile.ZipFile) -> list[str]:
    container = ET.fromstring(archive.read("META-INF/container.xml"))
    rootfile = container.find(".//{*}rootfile")
    if rootfile is None:
        raise ValueError("EPUB container has no rootfile")
    opf_path = rootfile.attrib["full-path"]
    opf_dir = Path(opf_path).parent
    opf_root = ET.fromstring(archive.read(opf_path))
    manifest = {}
    for item in opf_root.findall(".//{*}manifest/{*}item"):
        item_id = item.attrib.get("id")
        href = item.attrib.get("href")
        if item_id and href:
            manifest[item_id] = unquote((opf_dir / href).as_posix())
    return [
        manifest[itemref.attrib["idref"]]
        for itemref in opf_root.findall(".//{*}spine/{*}itemref")
        if itemref.attrib.get("idref") in manifest
    ]


def extract_epub(
    registry_path: Path,
    file_id: str,
    output_path: Path,
    allowed_output_root: Path,
    expected_work_id: str | None = None,
    max_chapters: int | None = None,
) -> dict:
    registry = load_json(registry_path)
    record = find_file(registry, file_id)
    if record["format"] != ".epub":
        raise ValueError(f"{file_id} is not an EPUB")
    if expected_work_id and record["work_id"] != expected_work_id:
        raise ValueError(
            f"Cross-work access blocked: requested {expected_work_id}, file belongs to {record['work_id']}"
        )

    source_path = absolute_source_path(registry, record)
    output_path = safe_output_path(output_path, allowed_output_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    chapters_written = 0
    with zipfile.ZipFile(source_path) as archive, output_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        spine = epub_spine(archive)
        if max_chapters is not None:
            spine = spine[:max_chapters]
        for chapter_href in spine:
            if chapter_href not in archive.namelist():
                raise ValueError(f"EPUB spine item missing: {chapter_href}")
            document = html.fromstring(archive.read(chapter_href))
            current_heading = ""
            paragraph_index = 0
            chapter_rows = 0
            for node in document.xpath("//h1|//h2|//h3|//h4|//h5|//h6|//p|//li|//blockquote"):
                text = re.sub(r"\s+", " ", node.text_content()).strip()
                if not text:
                    continue
                if node.tag.lower().startswith("h"):
                    current_heading = text
                    continue
                paragraph_index += 1
                row = {
                    "file_id": file_id,
                    "source_sha256": record["sha256"],
                    "work_id": record["work_id"],
                    "edition_id": record["edition_id"],
                    "locator": {
                        "type": "epub_anchor",
                        "chapter_href": chapter_href,
                        "heading": current_heading,
                        "paragraph_index": paragraph_index,
                        "text_hash": short_text_hash(text),
                    },
                    "evidence_status": "text_layer",
                    "text": text,
                }
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                rows_written += 1
                chapter_rows += 1
            if chapter_rows:
                chapters_written += 1
    return {
        "file_id": file_id,
        "chapters_written": chapters_written,
        "paragraphs_written": rows_written,
        "output": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--file-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allowed-output-root", type=Path, required=True)
    parser.add_argument("--expected-work-id")
    parser.add_argument("--max-chapters", type=int)
    args = parser.parse_args()
    result = extract_epub(
        args.registry,
        args.file_id,
        args.output,
        args.allowed_output_root,
        args.expected_work_id,
        args.max_chapters,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
