from __future__ import annotations

import argparse
from pathlib import Path

from common import load_json, utc_now, write_json


def requirement(name: str, passed: bool, evidence: list[str], detail: str) -> dict:
    return {
        "requirement": name,
        "status": "pass" if passed else "fail",
        "evidence": evidence,
        "detail": detail,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    qa = args.root / "核验"

    registry = load_json(qa / "source-registry-validation.json")
    tests = load_json(qa / "g01-test-report.json")
    staleness = load_json(qa / "staleness-audit.json")
    ocr = load_json(qa / "ocr-evidence-validation.json")
    boundary = load_json(qa / "g01-boundary-audit.json")
    artifacts = load_json(qa / "json-artifact-validation.json")

    requirements = [
        requirement(
            "五套理论、九部著作和全部原书文件具有三级身份与哈希",
            registry.get("status") == "pass"
            and registry.get("counts") == {"systems": 5, "works": 9, "editions": 11, "files": 19},
            ["来源/source-registry.json", "核验/source-registry-validation.json"],
            "5 systems, 9 works, 11 editions, 19 files; no stale hashes.",
        ),
        requirement(
            "PDF与EPUB双轨提取和定位可执行",
            tests.get("status") == "pass"
            and all(
                any(test.get("name") == name and test.get("status") == "pass" for test in tests["tests"])
                for name in (
                    "synthetic PDF extraction",
                    "synthetic EPUB extraction",
                    "valid EPUB anchor",
                    "fabricated EPUB page blocked",
                )
            ),
            ["脚本/extract_pdf.py", "脚本/extract_epub.py", "核验/g01-test-report.json"],
            "PDF page and EPUB anchor paths are separately validated.",
        ),
        requirement(
            "知识卡、章节地图、来源标签和G60前治理规则已建立",
            tests.get("status") == "pass" and tests.get("test_count", 0) >= 15,
            [
                "模式/knowledge-card.schema.json",
                "模式/chapter-map.schema.json",
                "核验/g01-test-report.json",
            ],
            "Positive and negative validation gates pass.",
        ),
        requirement(
            "来源变化能够定位失效产物并标记卡片重验",
            staleness.get("status") == "pass"
            and not staleness.get("untracked_artifacts")
            and any(
                test.get("name") == "stale card automatically marked for revalidation"
                and test.get("status") == "pass"
                for test in tests.get("tests", [])
            ),
            ["脚本/audit_staleness.py", "核验/staleness-audit.json", "核验/g01-test-report.json"],
            "All current artifacts are hash-tracked; synthetic stale card is marked.",
        ),
        requirement(
            "四本扫描书完成12页小样、人工真值和双引擎比较",
            ocr.get("status") == "pass"
            and ocr.get("counts", {}).get("books") == 4
            and ocr.get("counts", {}).get("sample_pages") == 48
            and ocr.get("counts", {}).get("ground_truth_targets") == 4,
            ["核验/ocr-evidence-validation.json", "核验/OCR小样结论.md"],
            "RapidOCR full samples and PaddleOCR targeted fallback are documented.",
        ),
        requirement(
            "原书与现有develop-screenplay-from-idea Skill未被修改且无正式知识产物",
            boundary.get("status") == "pass"
            and not boundary.get("source_files_modified_since_start")
            and not boundary.get("skill_files_modified_since_start")
            and not boundary.get("formal_knowledge_outputs"),
            ["核验/g01-boundary-audit.json"],
            "Boundary audit is anchored to the G01 start timestamp.",
        ),
        requirement(
            "全部结构化产物可解析",
            artifacts.get("status") == "pass" and not artifacts.get("errors"),
            ["核验/json-artifact-validation.json"],
            "JSON and JSONL artifacts parse successfully.",
        ),
    ]
    errors = [item["requirement"] for item in requirements if item["status"] != "pass"]
    report = {
        "checked_at": utc_now(),
        "goal": "G01",
        "status": "pass" if not errors else "fail",
        "failed_requirements": errors,
        "requirements": requirements,
    }
    write_json(args.report, report)
    print(f"G01 completion audit: {report['status']} ({len(requirements)} requirements)")
    for error in errors:
        print(f"ERROR: {error}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
