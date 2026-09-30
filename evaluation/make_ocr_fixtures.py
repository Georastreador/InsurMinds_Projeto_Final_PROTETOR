"""Builds OCR test documents from the synthetic residential policy (which has an answer key).

    python -m evaluation.make_ocr_fixtures

Outputs to data/ocr_test/: a fully scanned PDF (page images only, no text layer)
and a PNG of page 1. Both carry fictitious data only.
"""
from __future__ import annotations
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets" / "stress_test" / "synthetic_apolice_residencial.pdf"
OUT = ROOT / "data" / "ocr_test"
SCANNED_PDF = OUT / "synthetic_apolice_residencial_digitalizada.pdf"
PAGE_PNG = OUT / "synthetic_apolice_residencial_p1.png"


def build(dpi: int = 150) -> tuple[Path, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    src = pymupdf.open(str(SOURCE))
    scanned = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=dpi)
        new = scanned.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=pix.tobytes("png"))
    scanned.save(str(SCANNED_PDF)); scanned.close()
    src[0].get_pixmap(dpi=dpi).save(str(PAGE_PNG))
    src.close()
    return SCANNED_PDF, PAGE_PNG


if __name__ == "__main__":
    for path in build():
        print(path.relative_to(ROOT))
