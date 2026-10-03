"""Prompt-injection defence for document text.

Documents are data, never instructions. Two measures:
1. A3/Consulta wrap the document in <documento> tags and the system prompt states that
   anything inside them is content to analyse, not an instruction (llm/client.py).
2. This detector flags instruction-like passages addressed to an AI model, so the analyst
   sees the attempt in the warnings and in the trace. It does not alter the text: a
   contract may legitimately contain words such as "instruções".
"""
from __future__ import annotations

import re

from guardrails.verdict import fold

_PATTERNS = (
    r"\bignore\s+(?:all\s+|the\s+)?(?:previous|prior|above)\s+instructions?\b",
    r"\bdisregard\s+(?:all\s+|the\s+)?(?:previous|prior|above)\b",
    r"\bignor\w+\s+(?:todas\s+)?(?:as\s+)?instrucoes\s+(?:anteriores|acima|previas)\b",
    r"\bdesconsider\w+\s+(?:todas\s+)?(?:as\s+)?instrucoes\b",
    r"\b(?:you\s+are\s+now|act\s+as|voce\s+(?:agora\s+)?e\s+um[a]?\s+(?:assistente|modelo|ia))\b",
    r"\b(?:system\s+prompt|prompt\s+do\s+sistema|developer\s+message)\b",
    r"\b(?:assistant|assistente|modelo|ia|llm|chatgpt|gpt)\s*[:,]\s*(?:responda|answer|retorne|return|diga|say|classifique)\b",
    r"\b(?:retorne|return|responda|answer)\s+(?:apenas|only)\s+(?:que|that)\b",
    r"</?\s*(?:system|instructions?|documento)\s*>",
)
_RX = tuple(re.compile(p) for p in _PATTERNS)


def detect_injection(text: str, max_hits: int = 5) -> list[str]:
    """Short folded snippets around instruction-like passages (empty = nothing suspicious)."""
    folded = fold(text)
    hits = []
    for rx in _RX:
        for m in rx.finditer(folded):
            hits.append(folded[max(0, m.start() - 40): m.end() + 40])
            if len(hits) >= max_hits:
                return hits
    return hits


def neutralize_tags(text: str) -> str:
    """Prevent the document from closing the <documento> delimiter used in the prompt."""
    return re.sub(r"</?\s*documento\s*>", "[tag removida]", text, flags=re.I)
