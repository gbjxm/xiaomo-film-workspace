from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree as ET


CORE_EXTENSIONS = {".pdf", ".epub", ".mobi", ".azw3", ".txt", ".zip"}
SYSTEM_IDS = {"STC", "EGR", "TRU", "FLD", "MCK"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def short_text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def as_posix_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def resolve_single_glob(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    if len(matches) != 1:
        found = [str(item) for item in matches]
        raise ValueError(f"Pattern must resolve to exactly one file: {pattern!r}; found={found}")
    path = matches[0]
    if not path.is_file():
        raise ValueError(f"Resolved path is not a file: {path}")
    return path


def inspect_pdf(path: Path) -> dict[str, Any]:
    import fitz

    doc = fitz.open(path)
    page_count = doc.page_count
    text_pages = 0
    character_count = 0
    for page in doc:
        text = page.get_text("text")
        visible = re.sub(r"\s+", "", text)
        character_count += len(visible)
        if len(visible) >= 20:
            text_pages += 1
    metadata = {key: value for key, value in (doc.metadata or {}).items() if value}
    toc = doc.get_toc(simple=True)
    result = {
        "page_count": page_count,
        "encrypted": bool(doc.is_encrypted),
        "text_pages_ge_20_chars": text_pages,
        "text_page_ratio": round(text_pages / page_count, 4) if page_count else 0.0,
        "extracted_character_count": character_count,
        "toc_entries": len(toc),
        "metadata": metadata,
    }
    doc.close()
    return result


def _opf_root_from_epub(archive: zipfile.ZipFile) -> str:
    container = ET.fromstring(archive.read("META-INF/container.xml"))
    rootfile = container.find(".//{*}rootfile")
    if rootfile is None:
        raise ValueError("EPUB container has no rootfile")
    return rootfile.attrib["full-path"]


def inspect_epub(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        opf_path = _opf_root_from_epub(archive)
        opf_root = ET.fromstring(archive.read(opf_path))
        opf_dir = Path(opf_path).parent
        metadata_node = opf_root.find(".//{*}metadata")
        metadata: dict[str, list[str]] = {}
        if metadata_node is not None:
            for child in metadata_node:
                name = child.tag.rsplit("}", 1)[-1]
                text = (child.text or "").strip()
                if text:
                    metadata.setdefault(name, []).append(text)

        manifest: dict[str, dict[str, str]] = {}
        for item in opf_root.findall(".//{*}manifest/{*}item"):
            item_id = item.attrib.get("id")
            href = item.attrib.get("href")
            if item_id and href:
                normalized_href = unquote((opf_dir / href).as_posix())
                manifest[item_id] = {
                    "href": normalized_href,
                    "media_type": item.attrib.get("media-type", ""),
                    "properties": item.attrib.get("properties", ""),
                }

        spine_hrefs: list[str] = []
        for itemref in opf_root.findall(".//{*}spine/{*}itemref"):
            item = manifest.get(itemref.attrib.get("idref", ""))
            if item:
                spine_hrefs.append(item["href"])

        missing_spine_items = [href for href in spine_hrefs if href not in archive.namelist()]
        return {
            "opf_path": opf_path,
            "metadata": metadata,
            "manifest_items": len(manifest),
            "spine_items": len(spine_hrefs),
            "spine_hrefs": spine_hrefs,
            "missing_spine_items": missing_spine_items,
            "zip_entries": len(archive.namelist()),
        }


def locator_policy_for(format_suffix: str, ingestion: str) -> dict[str, Any]:
    suffix = format_suffix.lower()
    if suffix == ".pdf":
        return {
            "type": "pdf_page",
            "pdf_page_base": 1,
            "print_page": "explicit_only",
            "requires_text_hash": True,
            "source_method": "ocr" if ingestion == "ocr_required" else "text_layer",
        }
    if suffix == ".epub":
        return {
            "type": "epub_anchor",
            "requires": ["chapter_href", "heading", "paragraph_index", "text_hash"],
            "paragraph_index_base": 1,
            "fabricated_pages_forbidden": True,
        }
    return {"type": "none", "reason": f"{ingestion} files are not primary locators"}


def find_file(registry: dict[str, Any], file_id: str) -> dict[str, Any]:
    for item in registry.get("files", []):
        if item.get("file_id") == file_id:
            return item
    raise KeyError(f"Unknown file_id: {file_id}")


def absolute_source_path(registry: dict[str, Any], file_record: dict[str, Any]) -> Path:
    return Path(registry["source_root"]) / Path(file_record["relative_path"])


def system_from_card_id(card_id: str) -> str | None:
    match = re.fullmatch(r"(STC|EGR|TRU|FLD|MCK)-K\d{4}", card_id)
    return match.group(1) if match else None


def safe_output_path(path: Path, allowed_root: Path) -> Path:
    resolved = path.resolve()
    root = allowed_root.resolve()
    if os.path.commonpath([str(resolved), str(root)]) != str(root):
        raise ValueError(f"Output path escapes allowed root: {resolved}")
    return resolved

