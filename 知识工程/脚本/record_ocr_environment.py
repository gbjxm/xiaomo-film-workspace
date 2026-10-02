from __future__ import annotations

import argparse
import importlib.metadata
import platform
import sys
from pathlib import Path

from common import utc_now, write_json


PACKAGES = [
    "rapidocr",
    "onnxruntime",
    "paddleocr",
    "paddlepaddle",
    "paddlex",
    "opencv-contrib-python",
    "numpy",
    "pillow",
]


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "recorded_at": utc_now(),
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "packages": {name: package_version(name) for name in PACKAGES},
        "engines": {
            "rapidocr": {
                "backend": "onnxruntime CPU",
                "det_model": "PP-OCRv6_det_small",
                "rec_model": "PP-OCRv6_rec_small",
                "classification_model": "ch_ppocr_mobile_v2.0_cls_mobile",
            },
            "paddleocr": {
                "backend": "PaddlePaddle CPU, enable_mkldnn=False",
                "det_model": "PP-OCRv6_medium_det",
                "rec_model": "PP-OCRv6_medium_rec",
            },
        },
        "hardware_observed": {
            "memory_gb": 32,
            "gpu": "NVIDIA GeForce RTX 4060 Laptop GPU",
            "note": "本次为可复现的CPU比较；未安装Paddle GPU运行时。",
        },
    }
    write_json(args.output, report)
    print("OCR environment recorded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
