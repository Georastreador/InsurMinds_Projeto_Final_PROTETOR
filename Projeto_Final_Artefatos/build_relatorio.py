"""Gera o PDF do relatório técnico a partir do Markdown.

    python Projeto_Final_Artefatos/build_relatorio.py
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from tools.report_export import markdown_to_pdf  # noqa: E402

source = HERE / "Relatorio_Tecnico_InsurMinds_PROTETOR.md"
target = HERE / "Relatorio_Tecnico_InsurMinds_PROTETOR.pdf"
target.write_bytes(markdown_to_pdf(source.read_text(encoding="utf-8"), "InsurMinds_PROTETOR — Relatório Técnico"))
print(target.relative_to(HERE.parent))
