from __future__ import annotations
import re
from typing import Any
from pydantic import ValidationError
from schemas.policy import PolicySchema

class PolicyValidationError(ValueError):
    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None):
        super().__init__(message); self.errors = errors or []

def feedback_from_errors(exc: Exception, limit: int = 20) -> list[str]:
    """Compact, provider-neutral description of a retryable failure for the next A3 attempt."""
    errors = getattr(exc, "errors", None) or []
    lines = [f"{'.'.join(str(x) for x in e.get('loc', ()))}: {e.get('msg')}" for e in errors if isinstance(e, dict)]
    return lines[:limit] or [str(exc)]

def retry_warning(attempt: int, exc: Exception) -> str:
    """Technical, human-readable note for the audit tab (prefix 'A4:')."""
    detail = feedback_from_errors(exc, limit=2)
    first = (getattr(exc, "errors", None) or [{}])[0]
    value = f" (valor recebido: '{str(first.get('input'))[:60]}')" if isinstance(first, dict) and "input" in first else ""
    return f"A4: tentativa {attempt} rejeitada pela validação — {'; '.join(detail)}{value}. Nova tentativa solicitada ao A3."

class ValidationAgent:
    name = "A4_VALIDATION"

    @staticmethod
    def _clean_text(value: Any) -> Any:
        if isinstance(value, str):
            return re.sub(r"\s+", " ", value).strip()
        if isinstance(value, list):
            return [ValidationAgent._clean_text(v) for v in value]
        if isinstance(value, dict):
            return {k: ValidationAgent._clean_text(v) for k, v in value.items()}
        return value

    DATE_FIELDS = ("effective_date", "expiration_date", "retroactive_date")
    _BR_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")

    @classmethod
    def _normalize_dates(cls, candidate: dict[str, Any]) -> dict[str, Any]:
        """Brazilian documents use DD/MM/YYYY; the canonical schema uses ISO dates."""
        for field in cls.DATE_FIELDS:
            value = candidate.get(field)
            m = cls._BR_DATE.match(value) if isinstance(value, str) else None
            if m:
                day, month, year = m.groups()
                candidate[field] = f"{year}-{int(month):02d}-{int(day):02d}"
        return candidate

    # Individualized fields must name a concrete party/number. Conditions often only define the
    # role ("a Seguradora definida no frontispício da Apólice"); such text is not a fact of this policy.
    INDIVIDUALIZED_FIELDS = ("policy_number", "insurer", "insured_entity")
    _ROLE_DEFINITION = re.compile(
        r"especifica[cç][aã]o|frontisp[ií]cio|definid[ao]s? n[ao]|identificad[ao]s? n[ao]|indicad[ao]s? n[ao]|conforme aplic",
        re.IGNORECASE)

    @classmethod
    def _drop_role_definitions(cls, candidate: dict[str, Any]) -> dict[str, Any]:
        for field in cls.INDIVIDUALIZED_FIELDS:
            value = candidate.get(field)
            if isinstance(value, str) and cls._ROLE_DEFINITION.search(value):
                candidate[field] = None
                candidate["warnings"] = list(candidate.get("warnings") or []) + [
                    f"A4 guardrail: {field} continha definição genérica ('{value[:80]}'), não um valor individualizado; mantido como não identificado."]
        return candidate

    # reporting_period = period AFTER expiry to notify claims. Retroactivity is the period BEFORE
    # inception. v1.2 reference run (Sompo) stored retroactivity there and A5 compared it with
    # Chubb's "prazo complementar" as if they were the same concept.
    _RETRO = re.compile(r"retroativ|retroactiv|data retroa", re.IGNORECASE)
    _POST_EXPIRY = re.compile(
        r"prazo\s+(?:complementar|adicional|suplementar)|per[ií]odo\s+(?:complementar|adicional|suplementar)|"
        r"extended\s+reporting|discovery\s+period|ap[oó]s\s+o\s+(?:t[eé]rmino|fim|cancelamento)|"
        r"ap[oó]s\s+a\s+(?:expira|extin|rescis)", re.IGNORECASE)

    @classmethod
    def _text_of(cls, item: Any) -> str:
        if not isinstance(item, dict):
            return ""
        return " ".join(str(item.get(k) or "") for k in ("name", "title", "description", "category"))

    @classmethod
    def _fix_reporting_period(cls, candidate: dict[str, Any]) -> dict[str, Any]:
        warnings = list(candidate.get("warnings") or [])
        rp = candidate.get("reporting_period")
        if isinstance(rp, dict):
            text = str(rp.get("description") or "")
            if cls._RETRO.search(text) and not cls._POST_EXPIRY.search(text):
                candidate["reporting_period"] = rp = None
                warnings.append("A4 guardrail: reporting_period descrevia retroatividade (período anterior à vigência), "
                                "não prazo complementar; campo esvaziado.")
        if not rp:
            for group in ("extensions", "clauses", "coverages"):
                match = next((x for x in candidate.get(group) or []
                              if isinstance(x, dict) and (x.get("category") == "prazo_complementar"
                                                          or cls._POST_EXPIRY.search(cls._text_of(x)))), None)
                if match:
                    desc = " — ".join(str(match[k]) for k in ("name", "description") if match.get(k))
                    candidate["reporting_period"] = {"duration_days": None, "description": desc,
                                                     "source_reference": match.get("source_reference")}
                    warnings.append(f"A4 guardrail: reporting_period preenchido a partir de '{match.get('name')}' ({group}).")
                    break
        candidate["warnings"] = warnings
        return candidate

    def process(self, candidate: dict[str, Any]) -> PolicySchema:
        normalized = self._drop_role_definitions(self._normalize_dates(self._clean_text(candidate)))
        normalized = self._fix_reporting_period(normalized)
        try:
            return PolicySchema.model_validate(normalized)
        except ValidationError as exc:
            raise PolicyValidationError("Policy candidate failed schema validation", exc.errors()) from exc
