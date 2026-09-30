"""Deterministic mapping from PolicySchema output to Golden Dataset annotation fields.

The Golden Dataset v1.0 annotates some facts as concepts (e.g. `exclusion.cyber = true`,
`territorial_scope = WORLDWIDE_UNLESS_SPECIFIED`) rather than literal schema values.
Each resolver below is an explicit, auditable rule. Annotations with no slot in the
PolicySchema are classified OUT_OF_SCHEMA and excluded from EVAL-02/03 denominators;
they are reported separately for human review instead of being scored by guesswork.
"""
from __future__ import annotations
import re
import unicodedata
from typing import Any, Optional
from schemas.policy import PolicySchema, SourceReference

OUT_OF_SCHEMA = "OUT_OF_SCHEMA"

# Concept -> keywords searched in exclusion name/normalized_name/description.
EXCLUSION_CONCEPTS: dict[str, tuple[str, ...]] = {
    "environmental_damage": ("ambient", "environmental", "polui", "pollution"),
    "pollution": ("polui", "pollution", "ambient", "environmental"),
    "fines_penalties": ("multa", "fines", "penalt", "penalidade"),
    "cyber": ("ciber", "cyber"),
    "professional_liability": ("profissional", "professional"),
}

# Annotation fields that express contractual rules the schema does not model.
SCHEMA_GAPS = {"retention_rule", "retention.coverage_A", "retention.other", "defense_costs", "claims_basis"}


def _fold(text: Any) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def _refs(*refs: Optional[SourceReference]) -> list[SourceReference]:
    return [r for r in refs if r is not None]


def all_references(policy: PolicySchema) -> list[SourceReference]:
    """Every evidence reference in the policy, at any depth."""
    refs = list(policy.source_references)
    for group in (policy.coverages, policy.exclusions, policy.clauses, policy.extensions,
                  policy.insuring_agreements, policy.retentions):
        refs += _refs(*(x.source_reference for x in group))
    if policy.reporting_period:
        refs += _refs(policy.reporting_period.source_reference)
    return refs


def _refs_mentioning(policy: PolicySchema, *keywords: str) -> list[SourceReference]:
    return [r for r in all_references(policy)
            if any(k in _fold(f"{r.section} {r.excerpt}") for k in keywords)]


def resolve(policy: PolicySchema, field: str) -> tuple[Any, list[SourceReference]]:
    """Return (value comparable to the annotation, evidence references for that value)."""
    if field in SCHEMA_GAPS:
        return OUT_OF_SCHEMA, []

    if field == "policy_type":
        value = policy.policy_type
        if value and "d&o" in value.lower():
            value = "D&O"
        return value, _refs_mentioning(policy, "d&o", "diretores e administradores")

    if field == "territorial_scope":
        raw = _fold(policy.territorial_scope)
        refs = _refs_mentioning(policy, "mundo", "mundial", "geografic", "territori")
        if not raw:
            return None, refs
        worldwide = any(k in raw for k in ("mundo", "mundial", "worldwide"))
        unless = any(k in raw for k in ("salvo", "especificacao", "unless", "diversa"))
        if worldwide:
            return ("WORLDWIDE_UNLESS_SPECIFIED" if unless else "WORLDWIDE"), refs
        return policy.territorial_scope, refs

    m = re.fullmatch(r"insuring_agreements\.([ABC])\.present", field)
    if m:
        item = next((x for x in policy.insuring_agreements if x.side.value == m.group(1)), None)
        return (item.present if item else None), _refs(item.source_reference if item else None)

    if field.startswith("exclusion."):
        concept = field.split(".", 1)[1]
        keywords = EXCLUSION_CONCEPTS.get(concept)
        if not keywords:
            return OUT_OF_SCHEMA, []
        hits = [x for x in policy.exclusions
                if any(k in _fold(f"{x.normalized_name} {x.name} {x.description}") for k in keywords)]
        return (True if hits else None), _refs(*(x.source_reference for x in hits))

    value = getattr(policy, field, None)
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    elif hasattr(value, "isoformat"):
        value = value.isoformat()
    return value, []


def exclusion_concept_keys(comparison_fields: list[str], concept: str) -> list[str]:
    """A5 field names (exclusions:<key>) that express a Golden Dataset exclusion concept."""
    keywords = EXCLUSION_CONCEPTS.get(concept, ())
    return [f for f in comparison_fields
            if f.startswith("exclusions:") and any(k in _fold(f.split(":", 1)[1]) for k in keywords)]
