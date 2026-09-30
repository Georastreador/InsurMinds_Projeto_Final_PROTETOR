"""Export of the A6 executive synthesis as Markdown and PDF.

The PDF is rendered with PyMuPDF's Story API (HTML -> PDF), already a project
dependency, so accents and typographic characters are preserved without extra fonts.
"""
from __future__ import annotations
import html
import io
from datetime import datetime
from typing import Any, Optional

import markdown
import pymupdf

APP_NAME = "InsurMinds_PROTETOR"

_CSS = """
body { font-family: sans-serif; font-size: 10pt; line-height: 1.4; color: #1f2328; }
h1 { font-size: 16pt; color: #0b3d62; margin-bottom: 4pt; }
h2 { font-size: 12.5pt; color: #0b3d62; margin-top: 12pt; margin-bottom: 4pt; }
p, li { margin-bottom: 3pt; }
blockquote { color: #57606a; font-size: 9pt; margin-left: 8pt; }
.meta { font-size: 8.5pt; color: #57606a; }
em { color: #57606a; }
"""


def synthesis_markdown(report: str, metadata: Optional[dict[str, Any]] = None) -> str:
    """Synthesis with a provenance header, as distributed to the user."""
    meta = metadata or {}
    header = [f"<!-- {APP_NAME} · síntese exportada em {datetime.now():%d/%m/%Y %H:%M} -->"]
    if meta.get("run_id"):
        header.append(f"<!-- run_id: {meta['run_id']} · status: {meta.get('status', '')} -->")
    return "\n".join(header) + "\n\n" + report.strip() + "\n"


TABLE_CSS = """
table { border-collapse: collapse; width: 100%; margin: 4pt 0 8pt 0; font-size: 8.5pt; }
th { background-color: #e8eef4; text-align: left; padding: 3pt; border: 0.5pt solid #b8c4d0; }
td { padding: 3pt; border: 0.5pt solid #d0d7de; vertical-align: top; }
code { font-family: monospace; font-size: 8.5pt; }
h3 { font-size: 11pt; color: #0b3d62; margin-top: 8pt; }
"""


def markdown_to_pdf(text: str, title: str, header: Optional[str] = None, css: str = _CSS + TABLE_CSS) -> bytes:
    """Render Markdown (headings, lists, tables, emphasis) to an A4 PDF with page numbers."""
    body = markdown.markdown(text, extensions=["sane_lists", "tables"])
    page_html = (f'<p class="meta">{html.escape(header)}</p>' if header else "") + body

    buffer = io.BytesIO()
    writer = pymupdf.DocumentWriter(buffer)
    story = pymupdf.Story(html=page_html, user_css=css)
    page_rect = pymupdf.paper_rect("a4")
    content = page_rect + (50, 50, -50, -50)
    more = True
    while more:
        device = writer.begin_page(page_rect)
        more, _ = story.place(content)
        story.draw(device)
        writer.end_page()
    writer.close()

    # Page numbers are stamped afterwards, when the page count is known.
    doc = pymupdf.open(stream=buffer.getvalue(), filetype="pdf")
    for number, page in enumerate(doc, 1):
        page.insert_text((page_rect.width - 110, page_rect.height - 25), f"Página {number} de {doc.page_count}",
                         fontsize=8, color=(0.34, 0.38, 0.42))
    doc.set_metadata({"title": title, "creator": APP_NAME, "producer": APP_NAME})
    data = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return data


def synthesis_pdf(report: str, metadata: Optional[dict[str, Any]] = None) -> bytes:
    meta = metadata or {}
    details = [f"{APP_NAME}", f"exportado em {datetime.now():%d/%m/%Y %H:%M}"]
    if meta.get("run_id"):
        details.append(f"run {meta['run_id']}")
    if meta.get("duration"):
        details.append(f"processamento {meta['duration']}")
    return markdown_to_pdf(report, "Síntese comparativa", " · ".join(details))
