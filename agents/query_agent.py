"""Consulta: search and grounded Q&A over the stored documents (on demand, outside the A1–A6 run).

- search(): deterministic lookup of a theme across the structured items of every
  stored policy (no API call).
- QueryAgent.answer(): the LLM answers a question using only the most relevant pages
  of the selected documents' stored text; citations are checked against the pages it
  received and verdict language is refused.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from schemas.do_taxonomy import fold
from schemas.labels import CONCEPT_LABELS, display_name
from schemas.policy import PolicySchema
from storage.database import Database
from tools.text_budget import split_pages
from guardrails.verdict import VerdictGuard

GROUPS = {"coverages": "Cobertura", "extensions": "Extensão", "exclusions": "Exclusão",
          "clauses": "Cláusula", "retentions": "Franquia / retenção"}
_STOPWORDS = set("a o os as de da do das dos e em no na nos nas um uma para por com que qual quais como se ha há "
                 "é ser sao são ao aos à às ou the of and in".split())


@dataclass
class StoredDocument:
    document_id: str
    run_id: str
    created_at: str
    policy: PolicySchema

    @property
    def label(self) -> str:
        return f"{display_name(self.policy)} · {self.policy.source_file}"


def catalog(db: Database) -> list[StoredDocument]:
    """Latest structured version of each stored file (by file name), newest first."""
    seen, out = set(), []
    for document_id, run_id, payload, created_at in db.list_policies():
        policy = PolicySchema.model_validate_json(payload)
        if policy.source_file in seen:
            continue
        seen.add(policy.source_file)
        out.append(StoredDocument(document_id, run_id, created_at, policy))
    return out


def _items(policy: PolicySchema):
    for group in ("coverages", "extensions", "exclusions", "clauses"):
        for x in getattr(policy, group):
            category = CONCEPT_LABELS.get(x.category.value, "") if getattr(x, "category", None) else ""
            yield group, x.name, x.description or "", category, x.source_reference
    for r in policy.retentions:
        amount = f"{r.amount.currency or ''} {r.amount.amount}".strip() if r.amount and r.amount.amount is not None else ""
        yield "retentions", r.applies_to or "Franquia", " ".join(filter(None, [amount, r.conditions or ""])), "", r.source_reference


def _stem(word: str) -> str:
    """Light stem so 'cibernetico' matches 'cibernetica(s)' and 'franquias' matches 'franquia'."""
    return word[:-2] if len(word) > 6 and word[-2:] in ("os", "as", "es") else word[:-1] if len(word) > 5 and word[-1] in "aeos" else word


def search(documents: list[StoredDocument], term: str, groups: Optional[set[str]] = None) -> list[dict[str, Any]]:
    """Items whose name, description or concept matches every word of the term (accent-insensitive)."""
    words = [_stem(w) for w in fold(term).split() if w]
    rows = []
    for doc in documents:
        for group, name, description, category, ref in _items(doc.policy):
            if groups and group not in groups:
                continue
            haystack = fold(f"{name} {description} {category}")
            if words and all(w in haystack for w in words):
                rows.append({"Documento": doc.policy.source_file, "Seguradora": display_name(doc.policy),
                             "Ramo": doc.policy.line_of_business.value if doc.policy.line_of_business else "",
                             "Tipo": GROUPS[group], "Item": name, "Conceito": category,
                             "Descrição": description[:300], "Página": ref.page if ref else None})
    return rows


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9$%]+", fold(text)) if len(w) > 2 and w not in _STOPWORDS}


def retrieve_pages(raw_text: str, question: str, k: int = 6, max_chars: int = 30_000) -> list[dict]:
    """Top-k pages by term overlap with the question, returned in document order."""
    q = _tokens(question)
    pages = split_pages(raw_text)
    scored = []
    for p in pages:
        words = re.findall(r"[a-z0-9$%]+", fold(p["text"]))
        score = sum(1 for w in words if w in q)
        if score:
            scored.append((score, p))
    chosen, used = [], 0
    for _, p in sorted(scored, key=lambda s: -s[0])[:k]:
        if used + len(p["text"]) > max_chars:
            continue
        chosen.append(p); used += len(p["text"])
    return sorted(chosen, key=lambda p: p["page"])


class QueryResponder(Protocol):
    model: str
    def respond(self, question: str, context: str) -> dict[str, Any]: ...


class QueryAgent:
    name = "CONSULTA"

    def __init__(self, responder: Optional[QueryResponder] = None, guard: Optional[VerdictGuard] = None):
        self.responder = responder
        self.guard = guard or VerdictGuard()

    def answer(self, question: str, documents: list[tuple[str, StoredDocument, str]]) -> dict[str, Any]:
        """documents: (label 'A'/'B', stored document, raw text). Returns answer, citations and the pages used."""
        excerpts, context = {}, []
        for label, doc, raw in documents:
            pages = retrieve_pages(raw, question)
            excerpts[label] = pages
            context.append(f"=== Documento {label}: {doc.label} ===")
            context += [f"[{label} p.{p['page']}]\n{p['text'].strip()}" for p in pages]
        result = {"question": question, "excerpts": excerpts, "answer": None, "citations": [], "found": False, "note": None}
        if not any(excerpts.values()):
            result["note"] = "Nenhuma página dos documentos selecionados contém os termos da pergunta."
            return result
        if self.responder is None:
            result["note"] = "Resposta por IA disponível apenas no modo LIVE; abaixo, as páginas mais relevantes."
            return result
        try:
            out = self.responder.respond(question, "\n\n".join(context))
        except Exception as exc:
            result["note"] = f"Consulta à IA indisponível ({type(exc).__name__}); abaixo, as páginas mais relevantes."
            return result
        valid = {(label, p["page"]) for label, pages in excerpts.items() for p in pages}
        cited = [c for c in out.get("citations", []) if (c.get("doc"), c.get("page")) in valid]
        answer = out.get("answer", "")
        check = self.guard.check(answer)
        if check.blocked:
            result["note"] = f"Resposta descartada por conter linguagem de veredito ({check.reason})."
            return result
        dropped = len(out.get("citations", [])) - len(cited)
        result.update(answer=answer, citations=cited, found=bool(out.get("found")),
                      note=f"{dropped} citação(ões) fora das páginas consultadas foram descartadas." if dropped else None)
        return result
