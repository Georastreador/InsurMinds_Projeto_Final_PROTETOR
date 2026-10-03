"""Runtime Claim -> Evidence verification (deterministic, no API).

Every `source_reference` produced by A3 carries a page and a short "verbatim" excerpt
written by the LLM. v1.2 trusted both. This module checks each excerpt against the text
of the cited page and marks the reference:

- verified = True   -> the excerpt (or every segment of it, when abbreviated with "...")
                       is found on the cited page, exactly or with >= 90% similarity;
- verified = False  -> not found on the cited page; `verified_page` holds the page where
                       it was found instead, if any (wrong page cited);
- verified = None   -> nothing verifiable (no excerpt, or every segment shorter than
                       MIN_SEGMENT characters after normalization).

A5 lowers the confidence of items whose evidence is not confirmed and A6/UI show it.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Iterable, Optional

from schemas.policy import PolicySchema, SourceReference

MIN_SEGMENT = 12
FUZZY_THRESHOLD = 0.90
_ELLIPSIS = re.compile(r"\.{3,}|…|\[\s*\.{3}\s*\]|\(\s*\.{3}\s*\)")


def normalize(text: str) -> str:
    text = re.sub(r"-\s*\n\s*", "", text or "")          # hyphenation across lines
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9$%]+", " ", text)
    return " ".join(text.split())


def segments(excerpt: str) -> list[str]:
    return [s for s in (normalize(x) for x in _ELLIPSIS.split(excerpt or "")) if len(s) >= MIN_SEGMENT]


def _fuzzy_in(segment: str, haystack: str) -> bool:
    if segment in haystack:
        return True
    n = len(segment)
    if n > len(haystack) + 10:
        return False
    step = max(1, n // 4)
    for i in range(0, max(1, len(haystack) - n + 1), step):
        window = haystack[i:i + n + n // 10]
        sm = SequenceMatcher(None, segment, window, autojunk=False)
        if sm.real_quick_ratio() >= FUZZY_THRESHOLD and sm.quick_ratio() >= FUZZY_THRESHOLD and sm.ratio() >= FUZZY_THRESHOLD:
            return True
    return False


def found_in(excerpt: str, page_text: str) -> Optional[bool]:
    segs = segments(excerpt)
    if not segs:
        return None
    hay = normalize(page_text)
    return all(_fuzzy_in(s, hay) for s in segs)


def all_references(policy: PolicySchema) -> Iterable[SourceReference]:
    yield from policy.source_references
    for group in (policy.coverages, policy.exclusions, policy.clauses, policy.extensions,
                  policy.insuring_agreements, policy.retentions):
        for x in group:
            if x.source_reference is not None:
                yield x.source_reference
    if policy.reporting_period and policy.reporting_period.source_reference:
        yield policy.reporting_period.source_reference


def verify_policy(policy: PolicySchema, page_texts: list[dict[str, Any]],
                  alternate_texts: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    """Annotate every reference of `policy` in place and return summary statistics.

    `alternate_texts` (same page numbers) is tried too: A3 sees the PII-redacted text, so an
    excerpt may legitimately contain "[CPF]" where the original page has the number.
    """
    pages = {p["page"]: p.get("text") or "" for p in page_texts}
    alt = {p["page"]: p.get("text") or "" for p in (alternate_texts or [])}
    stats = {"references": 0, "verified": 0, "wrong_page": 0, "not_found": 0, "unverifiable": 0}
    wrong: list[dict[str, Any]] = []
    for ref in all_references(policy):
        stats["references"] += 1
        ref.verified, ref.verified_page = None, None
        if not segments(ref.excerpt or ""):
            stats["unverifiable"] += 1
            continue
        def on(page):
            hit = found_in(ref.excerpt, pages.get(page, ""))
            if not hit and page in alt:
                hit = found_in(ref.excerpt, alt[page])
            return hit
        if ref.page and on(ref.page):
            ref.verified = True; stats["verified"] += 1
            continue
        ref.verified = False
        other = next((n for n in pages if n != ref.page and on(n)), None)
        if other is not None:
            ref.verified_page = other; stats["wrong_page"] += 1
            wrong.append({"cited": ref.page, "found": other, "excerpt": (ref.excerpt or "")[:80]})
        else:
            stats["not_found"] += 1
    checkable = stats["references"] - stats["unverifiable"]
    stats["verified_rate"] = round(stats["verified"] / checkable, 3) if checkable else None
    stats["wrong_page_examples"] = wrong[:5]
    return stats


def summary_warning(label: str, stats: dict[str, Any]) -> Optional[str]:
    bad = stats["wrong_page"] + stats["not_found"]
    if not bad:
        return None
    return (f"{label}: {bad} de {stats['references'] - stats['unverifiable']} trecho(s) de evidência não foram "
            f"localizados literalmente na página citada ({stats['wrong_page']} em outra página, "
            f"{stats['not_found']} não localizados). Os itens afetados têm confiança reduzida e aparecem sinalizados.")
