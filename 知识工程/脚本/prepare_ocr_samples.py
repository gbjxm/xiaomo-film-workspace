from __future__ import annotations

import argparse
import math
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

from common import absolute_source_path, load_json, safe_output_path, utc_now, write_json


OCR_FILE_IDS = ["STC01-PDF-01", "STC02-PDF-01", "STC03-PDF-01", "EGR-PDF-01"]


def choose_pages(page_count: int) -> list[tuple[int, str]]:
    candidates = [
        (1, "封面或书名页"),
        (2, "前置页"),
        (4, "版权或前言候选"),
        (6, "目录或章节标题候选"),
        (8, "目录或章节标题候选"),
        (12, "前部正文候选"),
        (round(page_count * 0.15), "前部正文"),
        (round(page_count * 0.30), "普通正文与CER候选"),
        (round(page_count * 0.45), "中部正文"),
        (round(page_count * 0.60), "密集正文候选"),
        (round(page_count * 0.78), "后部特殊排版候选"),
        (round(page_count * 0.92), "后部正文"),
    ]
    result: list[tuple[int, str]] = []
    used: set[int] = set()
    for page, category in candidates:
        page = min(max(page, 1), page_count)
        if page not in used:
            result.append((page, category))
            used.add(page)
    cursor = 1
    while len(result) < 12:
        page = min(page_count, max(1, round(cursor * page_count / 13)))
        cursor += 1
        if page not in used:
            result.append((page, "补充代表页"))
            used.add(page)
    return sorted(result[:12], key=lambda item: item[0])


def render_page(doc: fitz.Document, pdf_page: int, output: Path, dpi: int) -> None:
    page = doc[pdf_page - 1]
    scale = dpi / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
    pixmap.save(output)


def make_cer_crop(page_image: Path, crop_output: Path) -> dict[str, int]:
    with Image.open(page_image) as image:
        width, height = image.size
        left = round(width * 0.04)
        top = round(height * 0.27)
        right = round(width * 0.96)
        bottom = round(height * 0.36)
        image.crop((left, top, right, bottom)).save(crop_output)
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def make_contact_sheet(samples: list[dict], output: Path) -> None:
    thumbs: list[tuple[Image.Image, str]] = []
    for sample in samples:
        image = Image.open(sample["image_path"]).convert("RGB")
        image.thumbnail((360, 500))
        thumbs.append((image.copy(), f"P{sample['pdf_page']} | {sample['category']}"))
        image.close()
    columns = 3
    cell_width, cell_height = 390, 555
    rows = math.ceil(len(thumbs) / columns)
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    font_path = Path(r"C:\Windows\Fonts\msyh.ttc")
    font = ImageFont.truetype(str(font_path), 16) if font_path.is_file() else ImageFont.load_default()
    for index, (image, label) in enumerate(thumbs):
        x = (index % columns) * cell_width + 15
        y = (index // columns) * cell_height + 10
        sheet.paste(image, (x, y + 28))
        draw.text((x, y), label, fill="black", font=font)
    sheet.save(output)


def prepare(registry_path: Path, output_root: Path, plan_output: Path, dpi: int) -> dict:
    registry = load_json(registry_path)
    files = {item["file_id"]: item for item in registry["files"]}
    output_root = safe_output_path(output_root, output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    books = []

    for file_id in OCR_FILE_IDS:
        record = files[file_id]
        if record["ingestion"] != "ocr_required":
            raise ValueError(f"{file_id} is not registered as ocr_required")
        source_path = absolute_source_path(registry, record)
        doc = fitz.open(source_path)
        book_dir = output_root / file_id
        book_dir.mkdir(parents=True, exist_ok=True)
        samples = []
        selected = choose_pages(doc.page_count)
        cer_page = min(selected, key=lambda item: abs(item[0] - round(doc.page_count * 0.30)))[0]
        crop_record = None
        for pdf_page, category in selected:
            image_path = book_dir / f"p{pdf_page:04d}.png"
            render_page(doc, pdf_page, image_path, dpi)
            sample = {
                "pdf_page": pdf_page,
                "category": category,
                "image_path": str(image_path.resolve()),
            }
            samples.append(sample)
            if pdf_page == cer_page:
                crop_path = book_dir / f"p{pdf_page:04d}_cer_crop.png"
                crop_box = make_cer_crop(image_path, crop_path)
                crop_record = {
                    "pdf_page": pdf_page,
                    "image_path": str(crop_path.resolve()),
                    "crop_box": crop_box,
                    "ground_truth_status": "pending_manual_transcription",
                }
        contact_sheet = book_dir / "contact-sheet.png"
        make_contact_sheet(samples, contact_sheet)
        books.append(
            {
                "file_id": file_id,
                "source_sha256": record["sha256"],
                "work_id": record["work_id"],
                "source_relative_path": record["relative_path"],
                "page_count": doc.page_count,
                "dpi": dpi,
                "samples": samples,
                "cer_target": crop_record,
                "contact_sheet": str(contact_sheet.resolve()),
            }
        )
        doc.close()

    plan = {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "sample_count_per_book": 12,
        "book_count": len(books),
        "books": books,
    }
    write_json(plan_output, plan)
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--plan-output", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=180)
    args = parser.parse_args()
    plan = prepare(args.registry, args.output_root, args.plan_output, args.dpi)
    print(f"Prepared {sum(len(book['samples']) for book in plan['books'])} OCR sample pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
