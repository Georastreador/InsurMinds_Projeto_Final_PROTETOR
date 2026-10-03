"""Verdict guardrail: no generated text may say which document is better or recommended.

Two layers, applied to every generated text (A5 reasons, A6 synthesis, Consulta answers):

1. Deterministic patterns (always on, zero cost). Accent-insensitive regular expressions
   for recommendation, preference, superiority and advantage language in Portuguese and
   English. Factual comparisons are preserved on purpose: "limite superior a R$ 10 mi",
   "cobertura mais ampla", "melhores esforços", "escolha do advogado" do not trigger.
2. Optional LLM classifier (LIVE). A cheap structured call that catches paraphrases the
   patterns miss. It only runs when layer 1 passes; if it fails, the text is judged by
   layer 1 alone and the failure is reported.

v1.2 used a list of 9 words; phrases such as "Recomenda-se contratar A" or "A é mais
vantajosa" passed. tests/test_verdict_guard.py keeps the adversarial set that motivated this.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional, Protocol

# Kept for backward compatibility (evaluation scripts import it); the patterns below are the guardrail.
PROHIBITED_VERDICTS = {"best", "worst", "better", "worse", "recommended",
                       "melhor", "pior", "recomendado", "recomendada"}


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


_NUMERIC_TAIL = r"(?!\s+(?:a|ao|aos|as|de|do|da|dos|das)\s*(?:r\$|us\$|\d|um\b|uma\b|dois|duas|tres|cem|mil|de\b|do\b|da\b))"

VERDICT_PATTERNS: tuple[tuple[str, str], ...] = (
    # Superlatives / direct value judgments
    ("melhor/pior", r"\b(?:melhor|pior)\b"),
    ("best/worst", r"\b(?:best|worst|better|worse)\b"),
    # Recommendation and advice
    ("recomendação", r"\brecomend\w*"),
    ("recommendation", r"\brecommend\w*"),
    ("aconselhamento", r"\baconselh\w*"),
    ("sugestão de contratação", r"\bsuger\w*(?:-se)?\s+(?:a\s+)?(?:contrata\w*|escolh\w*|opt\w*|adot\w*|prefer\w*)"),
    ("dever de escolha", r"\b(?:deve|devem|deveria|deveriam|convem|vale\s+a\s+pena)(?:-se)?\s+(?:(?!ser\b|estar\b|ter\b)\w+\s+)?(?!ser\b)(?:contrat\w*|escolh\w*|optar|prefer\w*|adotar|ficar\s+com)"),
    ("imperativo de escolha", r"\b(?:contrate|escolha|opte|prefira|fique\s+com)\s+(?:pela|pelo|a|o)\s+(?:apolice|documento|seguradora|proposta|opcao|alternativa|a\b|b\b)"),
    ("opção ideal", r"\b(?:opcao|alternativa|escolha|apolice|proposta|documento)\s+(?:ideal|certa|correta|preferivel|preferencial|indicada|recomendavel)\b"),
    ("vale a pena", r"\bvale\s+(?:mais\s+)?a\s+pena\b"),
    # Preference and advantage
    ("preferência", r"\bpreferi\w*vel\b|\bpreferable\b"),
    ("vantagem", r"\b(?:mais|menos)\s+(?:vantajos\w*|favoravel|favoraveis|benefic\w*|adequad\w*|indicad\w*|atrativ\w*|interessante\w*|protetiv\w*|segur[ao]s?|robust\w*|complet[ao]s?|competitiv\w*|generos\w*|solid[ao]s?)\b"),
    ("desvantagem", r"\b(?:desvantajos\w*|vantajos\w*\s+para|em\s+vantagem|em\s+desvantagem|leva\s+vantagem|sai\s+na\s+frente|supera\b|superam\b)"),
    ("advantage", r"\b(?:more|less)\s+(?:advantageous|favou?rable|beneficial|attractive|protective|suitable)\b|\badvantageous\b"),
    # Superiority (factual numeric comparisons such as "superior a R$ 10 mi" are allowed)
    ("superioridade", r"\b(?:e|sao|seria|seriam|parece|parecem|mostra-se|revela-se|torna-se|se\s+mostra)\s+(?:muito\s+|bem\s+|claramente\s+|nitidamente\s+)?(?:superior|inferior)(?:es)?\b" + _NUMERIC_TAIL),
    ("superiority", r"\b(?:superior|inferior)\s+to\s+(?:policy|document|insurer|a\b|b\b)"),
)

_COMPILED = tuple((label, re.compile(p)) for label, p in VERDICT_PATTERNS)


def verdict_matches(text: str) -> list[str]:
    """Labels of the verdict patterns found in text (empty list = no verdict)."""
    folded = fold(text)
    return [label for label, rx in _COMPILED if rx.search(folded)]


def has_verdict(text: str) -> bool:
    """Layer 1 only: deterministic verdict check, used where a model call is not justified."""
    return bool(verdict_matches(text))


class VerdictClassifier(Protocol):
    """Layer 2: returns {"verdict": bool, "reason": str}."""
    def classify(self, text: str) -> dict[str, Any]: ...


@dataclass
class VerdictCheck:
    blocked: bool
    layer: Optional[str] = None       # "patterns" | "classifier"
    reason: Optional[str] = None
    classifier_error: Optional[str] = None


class VerdictGuard:
    """Two-layer guardrail. Without a classifier it is exactly `has_verdict`."""

    def __init__(self, classifier: Optional[VerdictClassifier] = None):
        self.classifier = classifier

    def check(self, text: str) -> VerdictCheck:
        hits = verdict_matches(text)
        if hits:
            return VerdictCheck(True, "patterns", ", ".join(hits))
        if self.classifier is None or not (text or "").strip():
            return VerdictCheck(False)
        try:
            out = self.classifier.classify(text)
        except Exception as exc:  # the guardrail degrades to layer 1, never blocks the run
            return VerdictCheck(False, classifier_error=type(exc).__name__)
        if out.get("verdict"):
            return VerdictCheck(True, "classifier", str(out.get("reason") or "")[:200])
        return VerdictCheck(False)
