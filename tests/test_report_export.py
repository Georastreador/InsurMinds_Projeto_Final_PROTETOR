import pymupdf
from tools.report_export import synthesis_markdown, synthesis_pdf

REPORT = """# Síntese comparativa — Chubb × Sompo

## Principais diferenças (1 de 1)
1. **Franquias / retenções** — Ação, exclusão e cobertura diferem. _(A p. 8 · B p. 39 · Diferente)_

> Síntese gerada por IA. Não constitui recomendação jurídica."""


def test_markdown_export_keeps_report_and_adds_provenance():
    md = synthesis_markdown(REPORT, {"run_id": "r-1", "status": "COMPLETED"})
    assert REPORT.strip() in md and "run_id: r-1" in md


def test_pdf_export_renders_text_with_accents():
    data = synthesis_pdf(REPORT, {"run_id": "r-1", "duration": "3 min"})
    doc = pymupdf.open(stream=data, filetype="pdf")
    text = doc[0].get_text()
    assert data.startswith(b"%PDF")
    for fragment in ("Síntese comparativa", "Franquias", "Ação, exclusão", "A p. 8", "run r-1", "Página 1 de 1"):
        assert fragment in text


def test_pdf_export_paginates_long_reports():
    long_report = "# Síntese\n\n" + "\n".join(f"{i}. **Item {i}** — texto de diferença contratual." for i in range(1, 200))
    doc = pymupdf.open(stream=synthesis_pdf(long_report), filetype="pdf")
    assert doc.page_count > 1 and f"Página {doc.page_count} de {doc.page_count}" in doc[-1].get_text()
