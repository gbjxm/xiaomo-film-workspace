from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from common import load_json, safe_output_path, utc_now, write_json


def normalize_result_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for line in lines:
        text = str(line.get("text", "")).strip()
        if text:
            normalized.append(
                {
                    "text": text,
                    "confidence": round(float(line.get("confidence", 0.0)), 6),
                    "box": line.get("box"),
                }
            )
    return normalized


class RapidAdapter:
    name = "rapidocr"

    def __init__(self) -> None:
        try:
            from rapidocr import RapidOCR
        except ImportError:
            from rapidocr_onnxruntime import RapidOCR
        self.engine = RapidOCR()

    def recognize(self, image_path: Path) -> list[dict[str, Any]]:
        result = self.engine(str(image_path))
        if isinstance(result, tuple):
            items = result[0] or []
            return normalize_result_lines(
                [
                    {"box": item[0], "text": item[1], "confidence": item[2]}
                    for item in items
                    if len(item) >= 3
                ]
            )
        texts = getattr(result, "txts", None)
        scores = getattr(result, "scores", None)
        boxes = getattr(result, "boxes", None)
        if texts is not None:
            return normalize_result_lines(
                [
                    {
                        "box": boxes[index].tolist() if hasattr(boxes[index], "tolist") else boxes[index],
                        "text": text,
                        "confidence": scores[index] if scores is not None else 0.0,
                    }
                    for index, text in enumerate(texts)
                ]
            )
        raise RuntimeError(f"Unsupported RapidOCR result type: {type(result)!r}")


class PaddleAdapter:
    name = "paddleocr"

    def __init__(self) -> None:
        from paddleocr import PaddleOCR

        try:
            self.engine = PaddleOCR(
                lang="ch",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=False,
            )
            self.mode = "predict"
        except TypeError:
            self.engine = PaddleOCR(
                lang="ch",
                use_angle_cls=True,
                show_log=False,
                enable_mkldnn=False,
            )
            self.mode = "legacy"

    @staticmethod
    def _from_predict_item(item: Any) -> list[dict[str, Any]]:
        payload = getattr(item, "json", item)
        if callable(payload):
            payload = payload()
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(payload, dict) and "res" in payload:
            payload = payload["res"]
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unsupported PaddleOCR predict item: {type(payload)!r}")
        texts = payload.get("rec_texts", [])
        scores = payload.get("rec_scores", [])
        boxes = payload.get("rec_polys") or payload.get("dt_polys") or []
        return normalize_result_lines(
            [
                {
                    "text": text,
                    "confidence": scores[index] if index < len(scores) else 0.0,
                    "box": boxes[index].tolist() if index < len(boxes) and hasattr(boxes[index], "tolist") else (boxes[index] if index < len(boxes) else None),
                }
                for index, text in enumerate(texts)
            ]
        )

    def recognize(self, image_path: Path) -> list[dict[str, Any]]:
        if self.mode == "predict":
            result = self.engine.predict(str(image_path))
            lines = []
            for item in result:
                lines.extend(self._from_predict_item(item))
            return lines
        result = self.engine.ocr(str(image_path), cls=True)
        rows = result[0] if result and isinstance(result[0], list) else result
        return normalize_result_lines(
            [
                {"box": item[0], "text": item[1][0], "confidence": item[1][1]}
                for item in rows
                if item and len(item) >= 2
            ]
        )


def adapter_for(name: str):
    if name == "rapidocr":
        return RapidAdapter()
    if name == "paddleocr":
        return PaddleAdapter()
    raise ValueError(name)


def benchmark(plan: dict, engine_name: str, only_kind: str | None = None) -> dict:
    adapter = adapter_for(engine_name)
    results = []
    for book in plan["books"]:
        images = [
            {
                "kind": "full_page",
                "pdf_page": sample["pdf_page"],
                "image_path": sample["image_path"],
                "category": sample["category"],
            }
            for sample in book["samples"]
        ]
        target = book.get("cer_target")
        if target:
            images.append(
                {
                    "kind": "cer_crop",
                    "pdf_page": target["pdf_page"],
                    "image_path": target["image_path"],
                    "category": "CER人工真值裁切",
                }
            )
        if only_kind:
            images = [image for image in images if image["kind"] == only_kind]
        for image in images:
            started = time.perf_counter()
            error = None
            lines: list[dict[str, Any]] = []
            try:
                lines = adapter.recognize(Path(image["image_path"]))
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            elapsed = time.perf_counter() - started
            results.append(
                {
                    "engine": engine_name,
                    "file_id": book["file_id"],
                    "source_sha256": book["source_sha256"],
                    "work_id": book["work_id"],
                    **image,
                    "elapsed_seconds": round(elapsed, 4),
                    "line_count": len(lines),
                    "mean_confidence": round(
                        statistics.fmean(line["confidence"] for line in lines), 6
                    )
                    if lines
                    else None,
                    "text": "\n".join(line["text"] for line in lines),
                    "lines": lines,
                    "error": error,
                }
            )
    success_times = [row["elapsed_seconds"] for row in results if not row["error"]]
    return {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "engine": engine_name,
        "result_count": len(results),
        "success_count": sum(not row["error"] for row in results),
        "failure_count": sum(bool(row["error"]) for row in results),
        "mean_elapsed_seconds": round(statistics.fmean(success_times), 4) if success_times else None,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-plan", type=Path, required=True)
    parser.add_argument("--engine", choices=["rapidocr", "paddleocr"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allowed-output-root", type=Path, required=True)
    parser.add_argument("--only-kind", choices=["full_page", "cer_crop"])
    args = parser.parse_args()
    output = safe_output_path(args.output, args.allowed_output_root)
    report = benchmark(load_json(args.sample_plan), args.engine, args.only_kind)
    write_json(output, report)
    print(
        f"{args.engine}: {report['success_count']}/{report['result_count']} images; "
        f"mean={report['mean_elapsed_seconds']}s"
    )
    return 0 if report["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
