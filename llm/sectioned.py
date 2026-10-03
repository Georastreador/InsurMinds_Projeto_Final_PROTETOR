"""Sectioned A3 extraction: several calls over contiguous page windows, merged deterministically.

Motivation (v1.2 reference run): one call over up to 300 thousand characters produced only
2 generic coverage items for Sompo and put retroactivity in `reporting_period`. Smaller
windows give the model less text to cover per call, which tends to raise recall on long
documents; the merge keeps the first non-null scalar (in page order), reports conflicts,
and de-duplicates list items by (name, category).

Opt-in: OPENAI_EXTRACTION_MODE=sectioned (window size: SECTION_CHARS, default 80 000).
Status: validated offline with test doubles; NOT yet measured in a LIVE run against the
golden dataset. Run `python -m evaluation.run_live_golden --live` with the mode enabled
and compare with `evaluation.aggregate_runs` before making it the default.
"""
from __future__ import annotations

import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from guardrails.verdict import fold
from tools.text_budget import join_pages, split_pages

LIST_FIELDS = ("retentions", "insuring_agreements", "coverages", "sublimits", "exclusions",
               "clauses", "extensions", "source_references")
MAJORITY_FIELDS = ("line_of_business", "document_kind")
DEFAULT_SECTION_CHARS = 80_000


def page_windows(raw_text: str, max_chars: int) -> list[str]:
    pages = split_pages(raw_text)
    windows, current, size = [], [], 0
    for p in pages:
        n = len(p["text"]) + 20
        if current and size + n > max_chars:
            windows.append(join_pages(current)); current, size = [], 0
        current.append(p); size += n
    if current:
        windows.append(join_pages(current))
    return windows


def _item_key(field: str, item: Any) -> Any:
    if not isinstance(item, dict):
        return repr(item)
    if field == "insuring_agreements":
        return item.get("side")
    if field == "source_references":
        return (item.get("page"), fold(str(item.get("excerpt") or ""))[:60])
    name = item.get("name") or item.get("applies_to") or item.get("title") or item.get("description") or ""
    return (fold(str(name))[:80], item.get("category"))


def merge_candidates(parts: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    warnings: list[str] = []
    conflicts: list[str] = []
    for field in LIST_FIELDS:
        seen, out = set(), []
        for part in parts:
            for item in part.get(field) or []:
                key = _item_key(field, item)
                if key in seen:
                    continue
                seen.add(key); out.append(item)
        merged[field] = out
    for field in MAJORITY_FIELDS:
        votes = Counter(p.get(field) for p in parts if p.get(field))
        merged[field] = votes.most_common(1)[0][0] if votes else None
    scalars = {k for p in parts for k in p} - set(LIST_FIELDS) - set(MAJORITY_FIELDS) - {"warnings", "extraction_confidence"}
    for field in sorted(scalars):
        values = [p.get(field) for p in parts if p.get(field) not in (None, "", [], {})]
        merged[field] = values[0] if values else None
        distinct = {repr(v) for v in values}
        if len(distinct) > 1:
            conflicts.append(field)
    confidences = [p.get("extraction_confidence") for p in parts if isinstance(p.get("extraction_confidence"), (int, float))]
    merged["extraction_confidence"] = min(confidences) if confidences else None
    for p in parts:
        warnings += list(p.get("warnings") or [])
    warnings.append(f"A3 seccionado: documento analisado em {len(parts)} janelas de páginas e consolidado.")
    if conflicts:
        warnings.append("A3 seccionado: valores divergentes entre janelas em " + ", ".join(conflicts)
                        + "; mantido o primeiro em ordem de página. Conferir.")
    merged["warnings"] = warnings
    return merged


class SectionedExtractionClient:
    """Wraps any StructuredLLMClient; documents that fit one window go straight to the base client."""

    def __init__(self, base: Any, section_chars: Optional[int] = None, max_workers: int = 3):
        self.base = base
        self.section_chars = section_chars or int(os.getenv("SECTION_CHARS", DEFAULT_SECTION_CHARS))
        self.max_workers = max_workers
        self.model = getattr(base, "model", None)
        self.supports_parallel = getattr(base, "supports_parallel", False)
        # Progress estimate: windows run concurrently, so the budget seen by the user is one window.
        self.max_input_chars = getattr(base, "max_input_chars", None)

    @property
    def ledger(self):
        return getattr(self.base, "ledger", None)

    @ledger.setter
    def ledger(self, value):
        if hasattr(self.base, "ledger") or hasattr(type(self.base), "ledger"):
            self.base.ledger = value

    def extract_policy(self, *, raw_text: str, document: dict[str, Any], schema: dict[str, Any],
                       feedback: list[str] | None = None) -> dict[str, Any]:
        windows = page_windows(raw_text, self.section_chars)
        if len(windows) <= 1:
            return self.base.extract_policy(raw_text=raw_text, document=document, schema=schema, feedback=feedback)

        def run(text):
            return self.base.extract_policy(raw_text=text, document=document, schema=schema, feedback=feedback)

        if self.supports_parallel:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                parts = list(pool.map(run, windows))
        else:
            parts = [run(w) for w in windows]
        return merge_candidates(parts)
