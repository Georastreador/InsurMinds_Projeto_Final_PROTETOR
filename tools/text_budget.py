"""Page markers and input-size budget for A3.

A2 emits text with explicit page markers so the LLM can cite page numbers
(Claim -> Evidence). When a document exceeds the input budget, pages are selected
deterministically: the first pages (specification/cover) are always kept, then the
pages with the most D&O-relevant terms, restored to original order. Omitted pages
are reported so the limitation is visible in warnings, never silent.
"""
from __future__ import annotations
import re

PAGE_MARKER = "[[PÁGINA {page}]]"
_MARKER_RE = re.compile(r"\[\[PÁGINA (\d+)\]\]\n?")

DO_TERMS = (
    "cobertura", "exclus", "franquia", "participação obrigatória", "limite máximo",
    "sublimite", "retroativ", "período complementar", "prazo adicional", "territor",
    "foro", "jurisdi", "vigência", "especificação", "segurado", "tomador",
    "diretor", "administrador", "custos de defesa", "sinistro", "reclamação",
    "cláusula", "extensão", "side a", "side b", "side c",
)


def join_pages(page_texts: list[dict]) -> str:
    return "\n".join(f"{PAGE_MARKER.format(page=p['page'])}\n{p['text']}" for p in page_texts).strip()


def split_pages(text: str) -> list[dict]:
    """Inverse of join_pages. Text without markers is treated as a single page."""
    parts = _MARKER_RE.split(text)
    if len(parts) == 1:
        return [{"page": 1, "text": text}]
    return [{"page": int(parts[i]), "text": parts[i + 1]} for i in range(1, len(parts) - 1, 2)]


def _relevance(text: str) -> int:
    lowered = text.lower()
    return sum(lowered.count(term) for term in DO_TERMS)


def fit_to_budget(text: str, max_chars: int, keep_first: int = 3) -> tuple[str, list[int]]:
    """Return (text within budget, omitted page numbers)."""
    if len(text) <= max_chars:
        return text, []
    pages = split_pages(text)
    rendered = {p["page"]: f"{PAGE_MARKER.format(page=p['page'])}\n{p['text']}" for p in pages}
    ranked = pages[:keep_first] + sorted(pages[keep_first:], key=lambda p: _relevance(p["text"]), reverse=True)
    selected, used = set(), 0
    for p in ranked:
        size = len(rendered[p["page"]]) + 1
        if used + size <= max_chars:
            selected.add(p["page"]); used += size
    if not selected:
        first = pages[0]["page"]
        return rendered[first][:max_chars], [p["page"] for p in pages[1:]]
    kept = "\n".join(rendered[p["page"]] for p in pages if p["page"] in selected)
    return kept, [p["page"] for p in pages if p["page"] not in selected]
