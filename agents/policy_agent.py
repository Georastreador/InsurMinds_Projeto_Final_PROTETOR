from __future__ import annotations
from typing import Any
from schemas.policy import PolicySchema
from llm.client import StructuredLLMClient

SYSTEM_RULES = (
    "Extract only information supported by the supplied policy text. "
    "Do not infer absent facts. Preserve source evidence when available. "
    "Return null or empty lists for information not identified."
)

class PolicyAnalysisAgent:
    name = "A3_D&O_ANALYSIS"

    def __init__(self, llm: StructuredLLMClient):
        self.llm = llm

    def process(self, *, raw_text: str, document: dict[str, Any], feedback: list[str] | None = None) -> dict[str, Any]:
        if not raw_text.strip():
            raise ValueError("A3 cannot analyze empty text")
        candidate = self.llm.extract_policy(
            raw_text=raw_text,
            document=document,
            schema=PolicySchema.model_json_schema(),
            feedback=feedback,
        )
        if not isinstance(candidate, dict):
            raise TypeError("A3 structured output must be a dictionary")
        # Identity fields are pipeline facts, not LLM guesses.
        candidate = dict(candidate)
        candidate["document_id"] = document["document_id"]
        candidate["source_file"] = document["filename"]
        return candidate
