from __future__ import annotations

import argparse
import copy
import json
import tempfile
import zipfile
from pathlib import Path

import fitz

from common import short_text_hash, utc_now, write_json
from audit_staleness import stale_cards
from extract_epub import extract_epub
from extract_pdf import extract_pdf
from validate_card import validate_card
from validate_card_collection import validate_collection
from validate_chapter_map import validate_chapter_map
from validate_registry import validate_registry

TEST_RESULTS: list[dict] = []


def make_fixture_epub(path: Path) -> None:
    mimetype = "application/epub+zip"
    container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
    opf = """<?xml version="1.0" encoding="utf-8"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>G01 synthetic EPUB</dc:title><dc:creator>Test</dc:creator>
  </metadata>
  <manifest><item id="c1" href="chapter1.xhtml" media-type="application/xhtml+xml"/></manifest>
  <spine><itemref idref="c1"/></spine>
</package>"""
    chapter = """<html xmlns="http://www.w3.org/1999/xhtml"><body>
<h1>测试章节</h1><p>这是用于验证EPUB定位的合成段落。</p><p>它不属于任何原书。</p>
</body></html>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", mimetype)
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", opf)
        archive.writestr("OEBPS/chapter1.xhtml", chapter)


def make_fixture_pdf(path: Path) -> None:
    doc = fitz.open()
    for number in range(1, 4):
        page = doc.new_page()
        page.insert_text((72, 72), f"G01 synthetic page {number}")
    doc.save(path)
    doc.close()


def fixture_registry(root: Path) -> dict:
    pdf_path = root / "fixture.pdf"
    epub_path = root / "fixture.epub"
    make_fixture_pdf(pdf_path)
    make_fixture_epub(epub_path)
    return {
        "schema_version": "1.0",
        "source_root": str(root),
        "systems": [
            {"system_id": system, "name": system, "author": "test"}
            for system in ["STC", "EGR", "TRU", "FLD", "MCK"]
        ],
        "works": [
            {"work_id": "STC-TEST", "system_id": "STC", "title": "test", "original_title": "test"},
            {"work_id": "EGR-TEST", "system_id": "EGR", "title": "test", "original_title": "test"},
            {"work_id": "TRU-TEST", "system_id": "TRU", "title": "test", "original_title": "test"},
            {"work_id": "FLD-TEST", "system_id": "FLD", "title": "test", "original_title": "test"},
            {"work_id": "MCK-TEST-A", "system_id": "MCK", "title": "test", "original_title": "test"},
            {"work_id": "MCK-TEST-B", "system_id": "MCK", "title": "test", "original_title": "test"},
            {"work_id": "MCK-TEST-C", "system_id": "MCK", "title": "test", "original_title": "test"},
            {"work_id": "MCK-STORY", "system_id": "MCK", "title": "故事", "original_title": "Story"},
            {"work_id": "TRU-ANATOMY", "system_id": "TRU", "title": "故事写作大师班", "original_title": "The Anatomy of Story"}
        ],
        "editions": [
            {"edition_id": "STC-TEST-PDF", "work_id": "STC-TEST"},
            {"edition_id": "EGR-TEST-EPUB", "work_id": "EGR-TEST"},
            {"edition_id": "MCK-STORY-TW", "work_id": "MCK-STORY"}
        ],
        "files": [
            {
                "file_id": "STC-TEST-PDF-01",
                "edition_id": "STC-TEST-PDF",
                "work_id": "STC-TEST",
                "system_id": "STC",
                "relative_path": "fixture.pdf",
                "sha256": "a" * 64,
                "format": ".pdf",
                "role": "canonical",
                "ingestion": "text_layer",
                "locator_policy": {"type": "pdf_page"},
                "inspection": {"page_count": 3}
            },
            {
                "file_id": "EGR-TEST-EPUB-01",
                "edition_id": "EGR-TEST-EPUB",
                "work_id": "EGR-TEST",
                "system_id": "EGR",
                "relative_path": "fixture.epub",
                "sha256": "b" * 64,
                "format": ".epub",
                "role": "canonical",
                "ingestion": "epub_structure",
                "locator_policy": {"type": "epub_anchor"},
                "inspection": {"spine_hrefs": ["OEBPS/chapter1.xhtml"]}
            },
            {
                "file_id": "MCK-STORY-PDF-TW",
                "edition_id": "MCK-STORY-TW",
                "work_id": "MCK-STORY",
                "system_id": "MCK",
                "relative_path": "fixture.pdf",
                "sha256": "c" * 64,
                "format": ".pdf",
                "role": "crosscheck",
                "ingestion": "text_layer",
                "locator_policy": {"type": "pdf_page"},
                "inspection": {"page_count": 3}
            }
        ],
        "ignored_files": [],
        "unmatched_files": []
    }


def valid_card() -> dict:
    return {
        "card_id": "STC-K0001",
        "concept_key": "synthetic-test-concept",
        "status": "approved",
        "system_id": "STC",
        "work_id": "STC-TEST",
        "edition_ids": ["STC-TEST-PDF"],
        "evidence": [
            {
                "file_id": "STC-TEST-PDF-01",
                "source_sha256": "a" * 64,
                "evidence_status": "text_layer",
                "locator": {
                    "type": "pdf_page",
                    "pdf_page": 2,
                    "print_page": None,
                    "text_hash": short_text_hash("synthetic")
                }
            }
        ],
        "author_claim": "[作者主张] 合成测试，不属于原书。",
        "operationalization": "[操作化整理] 合成测试。",
        "problem_solved": "验证卡片结构",
        "required_inputs": [],
        "generation_questions": [],
        "diagnostic_criteria": [],
        "revision_methods": [],
        "applicable_when": [],
        "prohibited_when": [],
        "common_misuses": [],
        "cross_book_relations": [],
        "ai_short_adaptation": {"label": "AI短片适配", "text": "合成测试"},
        "user_notes": [],
        "external_supplements": [],
        "validation_records": []
    }


def assert_status(name: str, report: dict, expected: str) -> None:
    actual = report["status"]
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected}, got {actual}: {report}")
    TEST_RESULTS.append({"name": name, "expected": expected, "actual": actual, "status": "pass"})
    print(f"PASS {name}: {actual}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="g01-tests-") as temp:
        root = Path(temp)
        registry = fixture_registry(root)
        registry_path = root / "registry.json"
        write_json(registry_path, registry)

        valid = valid_card()
        assert_status("valid card", validate_card(valid, registry), "pass")

        invalid_page = copy.deepcopy(valid)
        invalid_page["evidence"][0]["locator"]["pdf_page"] = 99
        assert_status("invented PDF page blocked", validate_card(invalid_page, registry), "fail")

        epub_card = copy.deepcopy(valid)
        epub_card.update(
            {
                "card_id": "EGR-K0001",
                "concept_key": "synthetic-epub-concept",
                "system_id": "EGR",
                "work_id": "EGR-TEST",
                "edition_ids": ["EGR-TEST-EPUB"],
            }
        )
        epub_card["evidence"] = [
            {
                "file_id": "EGR-TEST-EPUB-01",
                "source_sha256": "b" * 64,
                "evidence_status": "text_layer",
                "locator": {
                    "type": "epub_anchor",
                    "chapter_href": "OEBPS/chapter1.xhtml",
                    "heading": "测试章节",
                    "paragraph_index": 1,
                    "text_hash": short_text_hash("synthetic"),
                },
            }
        ]
        assert_status("valid EPUB anchor", validate_card(epub_card, registry), "pass")
        fabricated_epub_page = copy.deepcopy(epub_card)
        fabricated_epub_page["evidence"][0]["locator"] = {
            "type": "pdf_page",
            "pdf_page": 1,
            "print_page": None,
            "text_hash": short_text_hash("synthetic"),
        }
        assert_status(
            "fabricated EPUB page blocked",
            validate_card(fabricated_epub_page, registry),
            "fail",
        )

        cross_work = copy.deepcopy(valid)
        cross_work["evidence"][0]["file_id"] = "EGR-TEST-EPUB-01"
        cross_work["evidence"][0]["locator"] = {
            "type": "epub_anchor",
            "chapter_href": "OEBPS/chapter1.xhtml",
            "heading": "测试章节",
            "paragraph_index": 1,
            "text_hash": short_text_hash("synthetic")
        }
        assert_status("cross-work evidence blocked", validate_card(cross_work, registry), "fail")

        ocr_unverified = copy.deepcopy(valid)
        ocr_unverified["evidence"][0]["evidence_status"] = "ocr_unverified"
        assert_status("unverified OCR blocked for approval", validate_card(ocr_unverified, registry), "fail")

        relation = copy.deepcopy(valid)
        relation["cross_book_relations"] = [
            {"target_card_id": "EGR-K0001", "relation_type": "related", "governance": "merged"}
        ]
        assert_status("pre-G60 merge blocked", validate_card(relation, registry), "fail")

        stale_hash = copy.deepcopy(valid)
        stale_hash["evidence"][0]["source_sha256"] = "f" * 64
        assert_status("changed source hash invalidates card", validate_card(stale_hash, registry), "fail")

        stale_dir = root / "stale-cards"
        stale_dir.mkdir()
        stale_path = stale_dir / "card.json"
        write_json(stale_path, valid)
        marked = stale_cards(
            stale_dir,
            {"STC-TEST-PDF-01": "d" * 64},
            apply=True,
        )
        marked_card = json.loads(stale_path.read_text(encoding="utf-8"))
        if len(marked) != 1 or marked_card["status"] != "revalidation_required":
            raise AssertionError({"marked": marked, "card": marked_card})
        TEST_RESULTS.append({"name": "stale card automatically marked for revalidation", "status": "pass"})
        print("PASS stale card automatically marked for revalidation")

        duplicate_concept = copy.deepcopy(valid)
        duplicate_concept["card_id"] = "STC-K0002"
        card_a_path = root / "card-a.json"
        card_b_path = root / "card-b.json"
        write_json(card_a_path, valid)
        write_json(card_b_path, duplicate_concept)
        assert_status(
            "duplicate concept key blocked",
            validate_collection([card_a_path, card_b_path], registry),
            "fail",
        )

        chapter_map = {
            "work_id": "STC-TEST",
            "edition_ids": ["STC-TEST-PDF"],
            "coverage_mode": "complete_map_selective_cards",
            "sections": [
                {
                    "section_id": "STC-TEST-S001",
                    "title": "合成章节",
                    "source_range": [],
                    "processing_status": "pending",
                    "main_topic": "",
                    "argument_progression": "",
                    "examples": [],
                    "actionability": {},
                    "exclusion_reason": "",
                }
            ],
        }
        assert_status("chapter-map template", validate_chapter_map(chapter_map, registry), "pass")

        pdf_output = root / "outputs" / "pdf.jsonl"
        result_pdf = extract_pdf(
            registry_path,
            "STC-TEST-PDF-01",
            pdf_output,
            root / "outputs",
            expected_work_id="STC-TEST",
            page_spec="1-2",
        )
        if result_pdf["pages_written"] != 2:
            raise AssertionError(result_pdf)
        TEST_RESULTS.append({"name": "synthetic PDF extraction", "status": "pass"})
        print("PASS synthetic PDF extraction")

        epub_output = root / "outputs" / "epub.jsonl"
        result_epub = extract_epub(
            registry_path,
            "EGR-TEST-EPUB-01",
            epub_output,
            root / "outputs",
            expected_work_id="EGR-TEST",
        )
        if result_epub["paragraphs_written"] != 2:
            raise AssertionError(result_epub)
        TEST_RESULTS.append({"name": "synthetic EPUB extraction", "status": "pass"})
        print("PASS synthetic EPUB extraction")

        try:
            extract_pdf(
                registry_path,
                "STC-TEST-PDF-01",
                root / "outputs" / "blocked.jsonl",
                root / "outputs",
                expected_work_id="EGR-TEST",
            )
        except ValueError:
            TEST_RESULTS.append({"name": "extractor cross-work guard", "status": "pass"})
            print("PASS extractor cross-work guard")
        else:
            raise AssertionError("Cross-work extractor access was not blocked")

        duplicate_registry = copy.deepcopy(registry)
        duplicate_registry["files"].append(copy.deepcopy(duplicate_registry["files"][0]))
        assert_status("duplicate file identity blocked", validate_registry(duplicate_registry), "fail")

    if args.report:
        write_json(
            args.report,
            {
                "checked_at": utc_now(),
                "status": "pass",
                "test_count": len(TEST_RESULTS),
                "tests": TEST_RESULTS,
            },
        )
    print("All G01 synthetic tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
