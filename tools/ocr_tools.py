"""OCR for scanned PDFs and images (A2 fallback).

Primary engine: the configured GPT model reading page images (no system install,
same credential as A3). Optional fallback: Tesseract, used only when the binary is
already installed (useful in DEMO/offline). Transcription is literal: the model is
instructed not to correct or complete text and to mark unreadable passages.
"""
from __future__ import annotations
import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional, Protocol

import pymupdf

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
OCR_DPI = 150
DEFAULT_MAX_OCR_PAGES = 40


class OCRNotConfiguredError(RuntimeError):
    pass


class OCREngine(Protocol):
    name: str
    def transcribe(self, images: list[tuple[int, bytes]]) -> dict[int, str]: ...


def render_pages(path: str | Path, pages: Optional[list[int]] = None, dpi: int = OCR_DPI) -> list[tuple[int, bytes]]:
    """PNG bytes per page (1-based numbers). Image files are a single page."""
    path = Path(path)
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        return [(1, path.read_bytes())]
    doc = pymupdf.open(str(path))
    wanted = pages or list(range(1, doc.page_count + 1))
    out = [(n, doc[n - 1].get_pixmap(dpi=dpi).tobytes("png")) for n in wanted]
    doc.close()
    return out


class GPTVisionOCR:
    """Literal transcription of page images with the configured OpenAI model, a few pages per call."""
    name = "OCR_GPT"
    PAGES_PER_CALL = 4
    PROMPT = (
        "Você é um OCR. Transcreva literalmente o texto de cada página de documento de seguro, em português, "
        "na ordem de leitura. Não corrija, não resuma e não complete palavras ou valores. Tabelas: uma linha por "
        "linha da tabela, células separadas por ' | '. Trechos ilegíveis: escreva [ilegível]. Texto puro, sem "
        "HTML nem Markdown. Responda uma entrada por página, com o número informado."
    )
    SCHEMA = {
        "type": "object",
        "properties": {"pages": {"type": "array", "items": {
            "type": "object", "properties": {"page": {"type": "integer"}, "text": {"type": "string"}},
            "required": ["page", "text"], "additionalProperties": False}}},
        "required": ["pages"], "additionalProperties": False,
    }

    ledger = None  # llm.usage.UsageLedger, attached by the Harness

    def __init__(self, *, model: str | None = None, api_key: str | None = None, client: Any = None):
        from llm.provider import make_openai_client, model_name
        self._client = client or make_openai_client(api_key)
        self.model = model_name(model)

    def transcribe(self, images: list[tuple[int, bytes]]) -> dict[int, str]:
        result: dict[int, str] = {}
        for i in range(0, len(images), self.PAGES_PER_CALL):
            batch = images[i:i + self.PAGES_PER_CALL]
            content: list[dict[str, Any]] = [{"type": "input_text", "text": self.PROMPT}]
            for number, png in batch:
                content.append({"type": "input_text", "text": f"Página {number}:"})
                content.append({"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(png).decode()})
            response = self._client.responses.create(
                model=self.model, input=[{"role": "user", "content": content}],
                text={"format": {"type": "json_schema", "name": "OCRPages", "schema": self.SCHEMA, "strict": True}},
            )
            from llm.usage import record
            record(self.ledger, "A2_ocr", response)
            wanted = {n for n, _ in batch}
            for page in json.loads(response.output_text)["pages"]:
                if page["page"] in wanted:
                    result[page["page"]] = _clean(page["text"])
        return result


class TesseractOCR:
    """Offline fallback; available only when the tesseract binary is installed."""
    name = "OCR_TESSERACT"

    @staticmethod
    def available() -> bool:
        return shutil.which("tesseract") is not None

    def transcribe(self, images: list[tuple[int, bytes]]) -> dict[int, str]:
        out = {}
        with tempfile.TemporaryDirectory() as td:
            for number, png in images:
                img = Path(td) / f"p{number}.png"
                img.write_bytes(png)
                done = subprocess.run(["tesseract", str(img), "stdout", "-l", "por"], capture_output=True, text=True, timeout=120)
                out[number] = done.stdout.strip()
        return out


def _clean(text: str) -> str:
    # Strip markup the model may still emit (e.g. <sup>678</sup>).
    return re.sub(r"</?(sup|sub|b|i|u|br)\s*/?>", "", text).strip()


def default_engine(ocr: Optional[OCREngine]) -> OCREngine:
    if ocr is not None:
        return ocr
    if TesseractOCR.available():
        return TesseractOCR()
    raise OCRNotConfiguredError(
        "Documento digitalizado ou imagem: o OCR requer o modo LIVE (GPT) ou o Tesseract instalado.")


def extract_with_ocr(file_path, pages: Optional[list[int]] = None, ocr: Optional[OCREngine] = None,
                     max_pages: Optional[int] = None) -> dict:
    """OCR of the given pages (all when None), capped at max_pages with the omission disclosed."""
    engine = default_engine(ocr)
    limit = max_pages or int(os.getenv("OCR_MAX_PAGES", DEFAULT_MAX_OCR_PAGES))
    path = Path(file_path)
    if pages is None:
        total = 1 if path.suffix.lower() in IMAGE_EXTENSIONS else pymupdf.open(str(path)).page_count
        pages = list(range(1, total + 1))
    selected, omitted = pages[:limit], pages[limit:]
    texts = engine.transcribe(render_pages(path, selected))
    warnings = []
    if omitted:
        warnings.append(f"OCR limitado a {limit} páginas; {len(omitted)} página(s) digitalizada(s) não lida(s): {omitted[:20]}"
                        + ("…" if len(omitted) > 20 else ""))
    return {"method": engine.name, "page_texts": [{"page": n, "text": texts.get(n, "")} for n in selected],
            "ocr_pages": selected, "omitted_pages": omitted, "warnings": warnings}
