"""Builds the LIVE components in one place (app, golden runner, stress runner).

Before v1.3 each entry point instantiated the adapters itself; options added here
(sectioned extraction, verdict classifier) now reach every entry point consistently.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

from guardrails.verdict import VerdictGuard


@dataclass
class LiveComponents:
    llm: Any
    semantic: Any
    writer: Any
    ocr: Any
    guard: VerdictGuard
    extraction_mode: str


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "sim", "on"}


def build_live_components(api_key: Optional[str] = None) -> LiveComponents:
    from llm.client import (OpenAISemanticComparator, OpenAIStructuredLLMClient, OpenAISynthesisWriter,
                            OpenAIVerdictClassifier)
    from llm.sectioned import SectionedExtractionClient
    from tools.ocr_tools import GPTVisionOCR

    llm: Any = OpenAIStructuredLLMClient(api_key=api_key)
    mode = os.getenv("OPENAI_EXTRACTION_MODE", "single").strip().lower()
    if mode == "sectioned":
        llm = SectionedExtractionClient(llm)
    classifier = OpenAIVerdictClassifier(api_key=api_key) if _flag("VERDICT_LLM_CHECK", "true") else None
    return LiveComponents(llm=llm, semantic=OpenAISemanticComparator(api_key=api_key),
                          writer=OpenAISynthesisWriter(api_key=api_key), ocr=GPTVisionOCR(api_key=api_key),
                          guard=VerdictGuard(classifier), extraction_mode=mode)
