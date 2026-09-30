import json
from pathlib import Path
import pymupdf
import pytest
from agents.extraction_agent import ExtractionAgent, ExtractionError
from agents.intake_agent import IntakeAgent
from tools.ocr_tools import GPTVisionOCR, extract_with_ocr, render_pages


class FakeOCR:
    name = "OCR_FAKE"
    def __init__(self): self.pages = []
    def transcribe(self, images):
        self.pages += [n for n, _ in images]
        return {n: f"texto OCR da página {n}" for n, _ in images}


def image_page(doc, text="imagem"):
    src = pymupdf.open(); src.new_page().insert_text((72, 72), text)
    png = src[0].get_pixmap(dpi=50).tobytes("png")
    page = doc.new_page(); page.insert_image(page.rect, stream=png)


def text_page(doc, text):
    doc.new_page().insert_text((72, 72), text)


def extract(path, ocr=None):
    return ExtractionAgent(ocr).process(IntakeAgent().process(path))


def test_scanned_pdf_is_read_by_ocr_with_page_markers(tmp_path):
    p = tmp_path / "scan.pdf"; d = pymupdf.open(); image_page(d); image_page(d); d.save(p)
    ocr = FakeOCR(); e = extract(p, ocr)
    assert e["method"] == "OCR_FAKE" and ocr.pages == [1, 2]
    assert "[[PÁGINA 2]]" in e["text"] and "texto OCR da página 2" in e["text"]


def test_mixed_pdf_only_ocrs_image_pages(tmp_path):
    p = tmp_path / "mixed.pdf"; d = pymupdf.open()
    text_page(d, "Condições gerais com texto nativo suficiente"); image_page(d); d.save(p)
    ocr = FakeOCR(); e = extract(p, ocr)
    assert ocr.pages == [2] and e["method"] == "PYMUPDF+OCR_FAKE"
    assert "texto nativo suficiente" in e["text"] and "texto OCR da página 2" in e["text"]
    assert any("OCR" in w for w in e["warnings"])


def test_short_text_page_without_images_is_not_ocr(tmp_path):
    p = tmp_path / "short.pdf"; d = pymupdf.open(); text_page(d, "A"); d.save(p)
    assert extract(p, FakeOCR())["method"] == "PYMUPDF"


def test_image_file_is_read_by_ocr(tmp_path):
    png = tmp_path / "apolice.png"
    src = pymupdf.open(); src.new_page().insert_text((72, 72), "x"); src[0].get_pixmap(dpi=50).save(png)
    e = extract(png, FakeOCR())
    assert e["method"] == "OCR_FAKE" and e["pages"] == 1


def test_scanned_document_without_engine_fails_with_clear_message(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.ocr_tools.TesseractOCR.available", staticmethod(lambda: False))
    p = tmp_path / "scan.pdf"; d = pymupdf.open(); image_page(d); d.save(p)
    with pytest.raises(ExtractionError, match="modo LIVE"):
        extract(p)


def test_ocr_page_cap_is_disclosed(tmp_path):
    p = tmp_path / "scan.pdf"; d = pymupdf.open()
    for _ in range(3): image_page(d)
    d.save(p)
    out = extract_with_ocr(p, ocr=FakeOCR(), max_pages=2)
    assert out["ocr_pages"] == [1, 2] and out["omitted_pages"] == [3] and "limitado a 2" in out["warnings"][0]


def test_gpt_ocr_batches_pages_and_strips_markup():
    class Responses:
        def __init__(self): self.calls = []
        def create(self, **req):
            self.calls.append(req)
            numbers = [int(c["text"].split()[1].rstrip(":")) for c in req["input"][0]["content"]
                       if c["type"] == "input_text" and c["text"].startswith("Página")]
            out = {"pages": [{"page": n, "text": f"CNPJ 12.345.<sup>678</sup>/0001 p{n}"} for n in numbers]}
            return type("R", (), {"output_text": json.dumps(out)})()
    responses = Responses()
    ocr = GPTVisionOCR(model="m", client=type("C", (), {"responses": responses})())
    texts = ocr.transcribe([(n, b"png") for n in range(1, 7)])
    assert len(responses.calls) == 2 and responses.calls[0]["text"]["format"]["strict"] is True
    assert texts[6] == "CNPJ 12.345.678/0001 p6"
