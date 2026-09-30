from __future__ import annotations
from pathlib import Path
import pymupdf
from .text_budget import join_pages

MIN_NATIVE_CHARS = 20

def extract_pdf_text(file_path: str | Path) -> dict:
    doc = pymupdf.open(str(file_path))
    pages=[]
    for i,page in enumerate(doc):
        pages.append({'page': i+1, 'text': page.get_text('text') or '', 'has_images': bool(page.get_images())})
    has_text=any(p['text'].strip() for p in pages)
    # Image-only pages (scans) need OCR; short pages without images are simply short.
    scanned=[p['page'] for p in pages if p['has_images'] and len(p['text'].strip()) < MIN_NATIVE_CHARS]
    # Page markers let A3 cite page numbers for Claim -> Evidence.
    text=join_pages(pages) if has_text else ''
    result={'pages': len(pages), 'page_texts': pages, 'text': text, 'characters_extracted': len(text), 'has_text': has_text, 'scanned_pages': scanned}
    doc.close(); return result
