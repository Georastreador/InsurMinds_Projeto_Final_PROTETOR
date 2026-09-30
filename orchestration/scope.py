"""Harness scope guardrail: which line of business each document belongs to.

D&O is the validated specialization. Other lines are still analyzed with the generic
schema fields, but the run states that clearly instead of silently treating them as D&O.
"""
from __future__ import annotations
from schemas.do_taxonomy import LINE_LABELS, DocumentKind, LineOfBusiness, detect_line_of_business
from schemas.policy import PolicySchema

VALIDATED = "D&O (escopo validado)"
PRESUMED = "D&O presumido (ramo não identificado)"
GENERIC = "Genérico (fora do escopo validado)"


def line_label(policy: PolicySchema) -> str:
    return LINE_LABELS[policy.line_of_business] if policy.line_of_business else "não identificado"


def is_do(policy: PolicySchema) -> bool:
    # Unknown line keeps the original D&O behaviour; only an explicit other line changes it.
    return policy.line_of_business in (None, LineOfBusiness.DO)


def assess_scope(policies: list[PolicySchema]) -> tuple[dict, list[str]]:
    warnings = []
    for p in policies:
        if p.line_of_business is None:
            warnings.append(f"Ramo de '{p.source_file}' não identificado; análise tratada como D&O sem confirmação.")
        elif p.line_of_business != LineOfBusiness.DO:
            warnings.append(
                f"'{p.source_file}' foi classificado como ramo {line_label(p)}: análise genérica de coberturas, "
                "exclusões, franquias e limites; a qualidade foi validada apenas para D&O.")
    lines = {p.line_of_business for p in policies if p.line_of_business}
    if len(lines) > 1:
        warnings.append("Documentos de ramos diferentes (" + " × ".join(line_label(p) for p in policies)
                        + "): a comparação de conceitos é limitada e muitos itens aparecerão como exclusivos.")
    kinds = [p.document_kind.value if p.document_kind else None for p in policies]
    scope = {
        "scope": (VALIDATED if all(p.line_of_business == LineOfBusiness.DO for p in policies)
                  else PRESUMED if all(is_do(p) for p in policies) else GENERIC),
        "lines_of_business": [line_label(p) for p in policies],
        "document_kinds": kinds,
        "general_conditions_only": all(k == DocumentKind.CONDICOES_GERAIS.value for k in kinds),
    }
    return scope, warnings


def reconcile_line_of_business(policy: PolicySchema, raw_text: str) -> str | None:
    """Fill an unclassified line ('outro' or missing) from the deterministic detector.

    The LLM classification is kept whenever it names a specific line; the detector only
    resolves the cases the model left open, and the override is disclosed as a warning.
    """
    if policy.line_of_business not in (None, LineOfBusiness.OUTRO):
        return None
    detected = detect_line_of_business(raw_text)
    if detected == LineOfBusiness.OUTRO:
        return None
    previous = policy.line_of_business.value if policy.line_of_business else "não informado"
    policy.line_of_business = detected
    note = (f"Ramo definido pelo detector determinístico como {LINE_LABELS[detected]} "
            f"(classificação do LLM: {previous}).")
    policy.warnings.append(note)
    return note
