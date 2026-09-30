"""Processing-time estimates and progress messages for the analyst.

Estimates are calibrated on the LIVE runs of 2026-09-30 (gpt-5.6-luna): A3 took
~15 s for a 2-page policy, ~40–90 s for 120–200 thousand characters and ~65 s for
a document capped at the 300 thousand character budget; A5 ~25–35 s; A6 ~15 s.
They are indications for the user, not guarantees.
"""
from __future__ import annotations
from typing import Callable, Optional

A3_BASE_S = 15
A3_CHARS_PER_S = 3500
A5_S = 30
A6_S = 15
OCR_S_PER_PAGE = 7  # GPT vision, 4 pages per call

ProgressCallback = Callable[[str, float], None]


def estimate_analysis_seconds(chars: int, budget: Optional[int]) -> int:
    """A3 (LLM structuring) time for one document; budget=None means an offline extractor."""
    if budget is None:
        return 1
    return int(A3_BASE_S + min(chars, budget) / A3_CHARS_PER_S)


def estimate_run_seconds(char_counts: list[int], budget: Optional[int]) -> int:
    if budget is None:
        return 2 + len(char_counts)
    return sum(estimate_analysis_seconds(c, budget) for c in char_counts) + A5_S + A6_S


def fmt_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes, rest = divmod(seconds, 60)
    return f"{minutes} min {rest:02d} s" if rest else f"{minutes} min"


def fmt_chars(chars: int) -> str:
    return f"{chars / 1000:.0f} mil caracteres" if chars >= 1000 else f"{chars} caracteres"


def fmt_pages(pages) -> str:
    return "? páginas" if not pages else f"{pages} página" if pages == 1 else f"{pages} páginas"


def estimate_ocr_seconds(scanned_pages: int, max_pages: int = 40) -> int:
    return OCR_S_PER_PAGE * min(scanned_pages, max_pages)
