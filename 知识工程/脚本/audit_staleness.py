from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from common import load_json, sha256_file, utc_now, write_json


EXCLUDED_PARTS = {
    ".venv-ocr",
    "__pycache__",
    "来源",
    "配置",
    "模式",
    "模板",
    "脚本",
    "规范",
}


def included(path: Path, root: Path) -> bool:
    return not any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts)


def iter_json_objects(path: Path) -> Iterable[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    value = json.loads(line)
                    if isinstance(value, dict):
                        yield value
        return
    value = load_json(path)
    if isinstance(value, dict):
        yield value
        for key in ("results", "books", "files", "rows", "targets"):
            children = value.get(key)
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, dict):
                        yield child


def current_source_hashes(registry: dict) -> tuple[dict[str, str], list[str]]:
    root = Path(registry["source_root"])
    expected = {item["file_id"]: item["sha256"] for item in registry["files"]}
    actual: dict[str, str] = {}
    changed: list[str] = []
    for item in registry["files"]:
        path = root / Path(item["relative_path"])
        digest = sha256_file(path) if path.is_file() else "missing"
        actual[item["file_id"]] = digest
        if digest != expected[item["file_id"]]:
            changed.append(item["file_id"])
    return actual, changed


def inspect_artifacts(
    artifact_root: Path, actual_hashes: dict[str, str]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    stale: list[dict[str, str]] = []
    untracked: list[dict[str, str]] = []
    candidates = [
        path
        for pattern in ("*.json", "*.jsonl")
        for path in artifact_root.rglob(pattern)
        if included(path, artifact_root)
    ]
    for path in sorted(set(candidates)):
        for value in iter_json_objects(path):
            file_id = value.get("file_id")
            source_sha = value.get("source_sha256")
            if not file_id or file_id not in actual_hashes:
                continue
            if not source_sha:
                untracked.append({"artifact": str(path.resolve()), "file_id": file_id})
                break
            if source_sha != actual_hashes[file_id]:
                stale.append(
                    {
                        "artifact": str(path.resolve()),
                        "file_id": file_id,
                        "recorded_sha256": source_sha,
                        "actual_sha256": actual_hashes[file_id],
                    }
                )
                break
    return stale, untracked


def stale_cards(card_root: Path | None, actual_hashes: dict[str, str], apply: bool) -> list[dict]:
    if card_root is None or not card_root.exists():
        return []
    stale: list[dict] = []
    for path in sorted(card_root.rglob("*.json")):
        card = load_json(path)
        affected = sorted(
            {
                evidence.get("file_id")
                for evidence in card.get("evidence", [])
                if evidence.get("file_id") in actual_hashes
                and evidence.get("source_sha256") != actual_hashes[evidence["file_id"]]
            }
        )
        if not affected:
            continue
        stale.append({"card": str(path.resolve()), "card_id": card.get("card_id"), "file_ids": affected})
        if apply:
            card["status"] = "revalidation_required"
            card.setdefault("validation_records", []).append(
                {
                    "checked_at": utc_now(),
                    "result": "revalidation_required",
                    "reason": "source_sha256_changed",
                    "file_ids": affected,
                }
            )
            write_json(path, card)
    return stale


def audit(registry: dict, artifact_root: Path, card_root: Path | None, apply_cards: bool) -> dict:
    actual_hashes, changed_files = current_source_hashes(registry)
    artifacts, untracked = inspect_artifacts(artifact_root, actual_hashes)
    cards = stale_cards(card_root, actual_hashes, apply_cards)
    return {
        "checked_at": utc_now(),
        "status": "pass"
        if not changed_files and not artifacts and not untracked and not cards
        else "revalidation_required",
        "changed_source_file_ids": changed_files,
        "stale_artifacts": artifacts,
        "untracked_artifacts": untracked,
        "stale_cards": cards,
        "cards_marked": bool(apply_cards and cards),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--card-root", type=Path)
    parser.add_argument("--apply-cards", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        load_json(args.registry),
        args.artifact_root,
        args.card_root,
        args.apply_cards,
    )
    write_json(args.report, report)
    print(
        f"Staleness audit: {report['status']}; "
        f"changed_sources={len(report['changed_source_file_ids'])}, "
        f"artifacts={len(report['stale_artifacts'])}, "
        f"untracked={len(report['untracked_artifacts'])}, cards={len(report['stale_cards'])}"
    )
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
