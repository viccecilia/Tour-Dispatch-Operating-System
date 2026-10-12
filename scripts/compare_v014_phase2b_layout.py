from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp" / "pdfs" / "layout-refinement"
OUTPUT = ROOT / "output" / "pdf" / "phase2b-layout-comparison"
DOWNLOADS = Path.home() / "Downloads"

DOCUMENTS = {
    "airport": (
        DOWNLOADS / "2026-10-05_姚博_7007_文书合并.pdf",
        ROOT / "output" / "pdf" / "V014_phase2b_airport_sample.pdf",
    ),
    "charter": (
        DOWNLOADS / "SL420326A_2026-10-10_包车文书合并.pdf",
        ROOT / "output" / "pdf" / "V014_phase2b_charter_sample.pdf",
    ),
}


def render(pdf: Path, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    prefix = destination / "page"
    subprocess.run(
        ["pdftoppm", "-png", "-r", "144", "-f", "1", "-l", "2", str(pdf), str(prefix)],
        check=True,
    )
    return sorted(destination.glob("page-*.png"))


def label_bar(image: Image.Image, label: str) -> Image.Image:
    result = Image.new("RGB", (image.width, image.height + 44), "white")
    result.paste(image.convert("RGB"), (0, 44))
    draw = ImageDraw.Draw(result)
    draw.text((16, 13), label, fill="#111111", font=ImageFont.load_default())
    draw.line((0, 43, image.width, 43), fill="#c9cdd3", width=1)
    return result


def overlay(target: Image.Image, current: Image.Image) -> Image.Image:
    target_gray = target.convert("L")
    current_gray = current.convert("L")
    canvas = Image.new("RGB", target.size, "white")
    target_layer = Image.new("RGBA", target.size, (224, 0, 160, 0))
    current_layer = Image.new("RGBA", current.size, (0, 150, 90, 0))
    target_layer.putalpha(target_gray.point(lambda value: 255 - value))
    current_layer.putalpha(current_gray.point(lambda value: 255 - value))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), target_layer)
    canvas = Image.alpha_composite(canvas, current_layer)
    return canvas.convert("RGB")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for document, (target_pdf, current_pdf) in DOCUMENTS.items():
        if not target_pdf.is_file():
            raise FileNotFoundError(target_pdf)
        if not current_pdf.is_file():
            raise FileNotFoundError(current_pdf)
        target_pages = render(target_pdf, TMP / f"target-{document}")
        current_pages = render(current_pdf, TMP / f"current-{document}")
        if len(target_pages) != len(current_pages):
            raise ValueError(f"page_count_mismatch:{document}:{len(target_pages)}:{len(current_pages)}")
        for page_number, (target_page, current_page) in enumerate(zip(target_pages, current_pages), 1):
            target = Image.open(target_page).convert("RGB")
            current = Image.open(current_page).convert("RGB")
            if current.size != target.size:
                current = current.resize(target.size, Image.Resampling.LANCZOS)
            target_output = OUTPUT / f"{document}-page-{page_number}-target.png"
            current_output = OUTPUT / f"{document}-page-{page_number}-current.png"
            shutil.copyfile(target_page, target_output)
            shutil.copyfile(current_page, current_output)
            target_labeled = label_bar(target, "TARGET")
            current_labeled = label_bar(current, "CURRENT REFINED")
            side_by_side = Image.new("RGB", (target_labeled.width * 2 + 12, target_labeled.height), "#d7dbe0")
            side_by_side.paste(target_labeled, (0, 0))
            side_by_side.paste(current_labeled, (target_labeled.width + 12, 0))
            side_by_side.save(OUTPUT / f"{document}-page-{page_number}-side-by-side.png")
            label_bar(overlay(target, current), "OVERLAY: target=magenta, current=green, overlap=dark").save(
                OUTPUT / f"{document}-page-{page_number}-overlay.png"
            )
    print(f"comparison_dir={OUTPUT}")


if __name__ == "__main__":
    main()
