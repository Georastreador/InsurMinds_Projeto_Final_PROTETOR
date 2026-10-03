"""Personal-data masking before text leaves the machine (LGPD).

Applied to the text sent to the provider by A3 and by the Consulta. Company identifiers
(CNPJ), policy numbers and amounts are kept: they are the object of the analysis and are
not personal data. CPF, e-mail and phone numbers of natural persons are replaced by tags.
Controlled by REDACT_PII (default on). OCR images cannot be masked; that limitation is
documented.
"""
from __future__ import annotations

import os
import re
from collections import Counter

_PATTERNS = (
    ("CPF", re.compile(r"(?<![\d./-])\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d|[./-]\d)|(?<=CPF[:\s])\s*\d{11}\b", re.I)),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("TELEFONE", re.compile(r"(?<![\d.,/])(?:\+?55\s?)?\(?\d{2}\)?\s?(?:9\s?)?\d{4}[-\s]\d{4}(?!\d|[.,/]\d)")),
)


def redaction_enabled() -> bool:
    return os.getenv("REDACT_PII", "true").strip().lower() not in {"0", "false", "no", "nao", "não"}


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    counts: Counter = Counter()
    for tag, rx in _PATTERNS:
        text, n = rx.subn(f"[{tag}]", text)
        counts[tag] += n
    return text, {k: v for k, v in counts.items() if v}


def maybe_redact(text: str) -> tuple[str, dict[str, int]]:
    return redact_pii(text) if redaction_enabled() else (text, {})
