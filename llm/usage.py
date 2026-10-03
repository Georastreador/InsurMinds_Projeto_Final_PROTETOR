"""Token and cost accounting per run and per stage (A2 OCR, A3, A5, A6, guardrail, Consulta).

Each LIVE adapter records `response.usage` in the ledger the Harness attaches to it.
Cost is estimated only when prices are configured (USD per million tokens):
OPENAI_PRICE_INPUT_PER_MTOK and OPENAI_PRICE_OUTPUT_PER_MTOK. No price is hard-coded,
because it depends on the model and changes over time.
"""
from __future__ import annotations

import os
import threading
from typing import Any, Optional


class UsageLedger:
    def __init__(self):
        self._lock = threading.Lock()
        self.stages: dict[str, dict[str, int]] = {}

    def record(self, stage: str, response: Any) -> None:
        usage = getattr(response, "usage", None)
        get = (lambda k: getattr(usage, k, None)) if usage is not None and not isinstance(usage, dict) else (lambda k: (usage or {}).get(k))
        tin = get("input_tokens") or get("prompt_tokens") or 0
        tout = get("output_tokens") or get("completion_tokens") or 0
        with self._lock:
            s = self.stages.setdefault(stage, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
            s["calls"] += 1; s["input_tokens"] += int(tin); s["output_tokens"] += int(tout)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            stages = {k: dict(v) for k, v in self.stages.items()}
        total = {"calls": sum(s["calls"] for s in stages.values()),
                 "input_tokens": sum(s["input_tokens"] for s in stages.values()),
                 "output_tokens": sum(s["output_tokens"] for s in stages.values())}
        pin, pout = os.getenv("OPENAI_PRICE_INPUT_PER_MTOK"), os.getenv("OPENAI_PRICE_OUTPUT_PER_MTOK")
        cost: Optional[float] = None
        if pin and pout:
            cost = round(total["input_tokens"] / 1e6 * float(pin) + total["output_tokens"] / 1e6 * float(pout), 4)
        return {"by_stage": stages, "total": total, "estimated_cost_usd": cost,
                "cost_note": None if cost is not None else "Defina OPENAI_PRICE_INPUT_PER_MTOK e OPENAI_PRICE_OUTPUT_PER_MTOK para estimar o custo."}


def record(ledger: Optional[UsageLedger], stage: str, response: Any) -> None:
    if ledger is not None:
        ledger.record(stage, response)
