from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import load_json, utc_now, write_json


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for index_a, char_a in enumerate(a, start=1):
        current = [index_a]
        for index_b, char_b in enumerate(b, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[index_b] + 1,
                    previous[index_b - 1] + (char_a != char_b),
                )
            )
        previous = current
    return previous[-1]


def evaluate(ground_truth: dict, engine_reports: list[dict]) -> dict:
    truth_by_key = {
        (item["file_id"], item["pdf_page"], item.get("kind", "cer_crop")): item
        for item in ground_truth["targets"]
    }
    rows = []
    for report in engine_reports:
        engine = report["engine"]
        for result in report["results"]:
            key = (result["file_id"], result["pdf_page"], result["kind"])
            truth = truth_by_key.get(key)
            if not truth:
                continue
            expected = normalize_text(truth["text"])
            actual = normalize_text(result.get("text", ""))
            distance = levenshtein(expected, actual)
            cer = distance / len(expected) if expected else None
            rows.append(
                {
                    "engine": engine,
                    "file_id": result["file_id"],
                    "pdf_page": result["pdf_page"],
                    "kind": result["kind"],
                    "ground_truth_characters": len(expected),
                    "ocr_characters": len(actual),
                    "edit_distance": distance,
                    "cer": round(cer, 6) if cer is not None else None,
                    "passes_2_percent": cer is not None and cer <= 0.02,
                }
            )
    summary = {}
    for engine in sorted({row["engine"] for row in rows}):
        engine_rows = [row for row in rows if row["engine"] == engine]
        weighted_errors = sum(row["edit_distance"] for row in engine_rows)
        weighted_chars = sum(row["ground_truth_characters"] for row in engine_rows)
        weighted_cer = weighted_errors / weighted_chars if weighted_chars else None
        summary[engine] = {
            "targets": len(engine_rows),
            "weighted_cer": round(weighted_cer, 6) if weighted_cer is not None else None,
            "passes_2_percent": weighted_cer is not None and weighted_cer <= 0.02,
        }
    return {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "normalization": "remove whitespace; normalize paired Chinese quotes",
        "rows": rows,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--engine-report", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(
        load_json(args.ground_truth),
        [load_json(path) for path in args.engine_report],
    )
    write_json(args.output, report)
    for engine, summary in report["summary"].items():
        print(f"{engine}: weighted CER={summary['weighted_cer']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
