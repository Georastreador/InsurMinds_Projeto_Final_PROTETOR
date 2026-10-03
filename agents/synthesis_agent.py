from __future__ import annotations
import re
from collections import Counter
from typing import Any, Optional, Protocol
from schemas.comparison import ComparisonResult, ComparisonStatus, FieldComparison
from schemas.do_taxonomy import fold
from schemas.labels import STATUS_LABELS, human_field, short_value

# The guardrail lives in guardrails/verdict.py; re-exported here for backward compatibility.
from guardrails.verdict import PROHIBITED_VERDICTS, VerdictGuard, has_verdict  # noqa: F401


MATERIAL = {ComparisonStatus.DIFFERENT, ComparisonStatus.ONLY_A, ComparisonStatus.ONLY_B, ComparisonStatus.REVIEW_REQUIRED}
MAX_KEY_DIFFERENCES = 8
MAX_REVIEW_POINTS = 6

# Contractual weight used to order items for the fallback and for the writer's input.
_PRIORITY = ("retentions", "limit_of_liability", "aggregate_limit", "insuring_side_", "reporting_period",
             "exclusions:", "coverages:", "territorial_scope", "retroactive_date", "jurisdiction", "clauses:")


def _detail(value: Any, limit: int = 900) -> Optional[str]:
    """Writer input: name plus description/conditions, long enough to avoid 'truncated' judgments."""
    if value is None:
        return None
    items = value if isinstance(value, list) else [value]
    parts = []
    for v in items:
        if isinstance(v, dict):
            text = " — ".join(str(v[k]) for k in ("name", "title", "applies_to", "description", "conditions")
                              if v.get(k) not in (None, "", [], {}))
            parts.append(text or short_value(v))
        else:
            parts.append(str(v))
    text = " | ".join(parts)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _priority(field: str) -> int:
    return next((i for i, p in enumerate(_PRIORITY) if field.startswith(p)), len(_PRIORITY))


class SynthesisWriter(Protocol):
    """Generative writer for A6. Returns {overview, key_differences[{id,summary}], review_points[{id,summary}]}."""
    model: str
    def write(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class SynthesisAgent:
    """A6: executive synthesis bounded by the A5 ComparisonResult.

    With a writer (LIVE), the LLM drafts the prose but may only reference comparison
    items by id; statuses and page evidence are attached deterministically from A5.
    Unknown ids are dropped and verdict language discards the draft in favour of the
    deterministic synthesis, so A6 never fails the run and never emits a verdict.
    """
    name = "A6_SYNTHESIS"

    def __init__(self, writer: Optional[SynthesisWriter] = None, guard: Optional[VerdictGuard] = None):
        self.writer = writer
        self.guard = guard or VerdictGuard()
        self.last_method = "deterministic"
        self.last_warning: Optional[str] = None
        self.last_guard: Optional[dict[str, Any]] = None

    # --- helpers ----------------------------------------------------------------
    @staticmethod
    def _pages(item: FieldComparison) -> str:
        parts = []
        for side, v in (("A", item.policy_a), ("B", item.policy_b)):
            if v.value is None:
                parts.append(f"{side} não identificado")
            elif not (v.source and v.source.page):
                parts.append(f"{side} sem página")
            elif v.source.verified is False and v.source.verified_page:
                parts.append(f"{side} p. {v.source.page} (trecho localizado na p. {v.source.verified_page})")
            elif v.source.verified is False:
                parts.append(f"{side} p. {v.source.page} (trecho não confirmado)")
            else:
                parts.append(f"{side} p. {v.source.page}")
        return " · ".join(parts)

    @staticmethod
    def _material(comparison: ComparisonResult) -> list[FieldComparison]:
        return sorted((x for x in comparison.fields if x.status in MATERIAL), key=lambda x: _priority(x.field))

    @staticmethod
    def _fallback_summary(item: FieldComparison) -> str:
        text = f"A: {short_value(item.policy_a.value, 120)} | B: {short_value(item.policy_b.value, 120)}"
        return f"{text}. {item.reason}" if item.reason else text

    @staticmethod
    def _has_verdict(text: str) -> bool:
        return has_verdict(text)

    def _payload(self, material, context) -> dict[str, Any]:
        return {
            "policy_a": context.get("name_a"), "policy_b": context.get("name_b"),
            "scope": context.get("scope"), "lines_of_business": context.get("lines_of_business"),
            "general_conditions_only": context.get("general_conditions_only"),
            "items": [{"id": x.field, "tema": human_field(x.field), "situacao": STATUS_LABELS[x.status.value],
                       "A": _detail(x.policy_a.value), "B": _detail(x.policy_b.value),
                       "criterio": (x.reason or "")[:300]} for x in material],
        }

    def _draft(self, material, context):
        """LLM draft mapped back onto A5 items, or None when the draft is unusable."""
        by_id = {x.field: x for x in material}
        try:
            draft = self.writer.write(self._payload(material, context))
        except Exception as exc:
            self.last_warning = f"A6: síntese generativa indisponível ({type(exc).__name__}); usada síntese determinística."
            return None
        key = [(by_id[d["id"]], d["summary"]) for d in draft.get("key_differences", []) if d.get("id") in by_id]
        review = [(by_id[d["id"]], d["summary"]) for d in draft.get("review_points", []) if d.get("id") in by_id]
        texts = [draft.get("overview", "")] + [s for _, s in key + review]
        check = self.guard.check("\n".join(texts))
        self.last_guard = {"blocked": check.blocked, "layer": check.layer, "reason": check.reason,
                           "classifier_error": check.classifier_error}
        if check.blocked:
            self.last_warning = (f"A6: síntese generativa descartada por conter linguagem de veredito "
                                 f"(camada {check.layer}: {check.reason}); usada síntese determinística.")
            return None
        return draft.get("overview", ""), key[:MAX_KEY_DIFFERENCES], review[:MAX_REVIEW_POINTS]

    # --- main -------------------------------------------------------------------
    def process(self, comparison: ComparisonResult, context: Optional[dict[str, Any]] = None) -> str:
        if comparison is None:
            raise ValueError("A6 requires a ComparisonResult")
        context = context or {}
        self.last_method, self.last_warning, self.last_guard = "deterministic", None, None
        counts = Counter(item.status.value for item in comparison.fields)
        material = self._material(comparison)

        draft = self._draft(material, context) if (self.writer and material) else None
        if draft:
            overview, key, review = draft
            self.last_method = f"generative ({getattr(self.writer, 'model', 'LLM')})"
        else:
            overview = (f"Foram comparados {len(comparison.fields)} itens; {len(material)} apresentam diferença, "
                        "exclusividade ou necessidade de revisão. Os itens abaixo estão ordenados por peso contratual "
                        "(franquias, limites, coberturas, exclusões).")
            key = [(x, self._fallback_summary(x)) for x in material if x.status != ComparisonStatus.REVIEW_REQUIRED][:MAX_KEY_DIFFERENCES]
            review = [(x, self._fallback_summary(x)) for x in material if x.status == ComparisonStatus.REVIEW_REQUIRED][:MAX_REVIEW_POINTS]

        name_a, name_b = context.get("name_a") or comparison.policy_a_document_id, context.get("name_b") or comparison.policy_b_document_id
        lines = [f"# Síntese comparativa — {name_a} × {name_b}", ""]
        if context.get("scope"):
            lines += [f"**Escopo:** {context['scope']} · Ramos: {' × '.join(context.get('lines_of_business') or [])}", ""]
        lines += ["## Visão geral", overview, "", f"## Principais diferenças ({len(key)} de {len(material)})"]
        if not key:
            lines.append("- Nenhuma diferença material foi identificada nos itens comparados.")
        for i, (item, summary) in enumerate(key, 1):
            lines.append(f"{i}. **{human_field(item.field)}** — {summary} _({self._pages(item)} · {STATUS_LABELS[item.status.value]})_")
        if review:
            lines += ["", "## Pontos que exigem leitura do texto integral"]
            lines += [f"- **{human_field(item.field)}** — {summary} _({self._pages(item)})_" for item, summary in review]
        lines += ["", "## Números da comparação",
                  f"- Campos comparados: {len(comparison.fields)} · Iguais: {counts.get('EQUAL', 0)} · "
                  f"Diferentes: {counts.get('DIFFERENT', 0)} · Somente A: {counts.get('ONLY_A', 0)} · "
                  f"Somente B: {counts.get('ONLY_B', 0)} · Revisão requerida: {counts.get('REVIEW_REQUIRED', 0)}"]
        if len(material) > len(key) + len(review):
            lines.append(f"- A lista completa de {len(material)} itens está na aba Comparação.")
        if context.get("general_conditions_only"):
            lines.append("- Documentos de condições gerais: número, vigência e valores constam da Especificação da Apólice.")
        method = "gerada por IA a partir do resultado da comparação (A5)" if self.last_method.startswith("generative") else "determinística"
        lines += ["", f"> Síntese {method}. Descreve diferenças documentais e não constitui recomendação jurídica, "
                      "avaliação de superioridade ou indicação de contratação. A decisão final é humana."]
        return "\n".join(lines)
