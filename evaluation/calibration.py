"""Calibration of the A5 semantic judge (self-reported confidence vs. reality).

The judge reports a confidence per pair and A5 escalates to human review below
A5_MIN_CONFIDENCE (0.7 by default). In the v1.2 reference run 0 of 102 items went to review.
This script shows, over the saved LIVE runs:

1. the distribution of the judge's confidence (are values ever below the threshold?);
2. how many items each threshold would send to review (to choose A5_MIN_CONFIDENCE);
3. accuracy per confidence band on the items that the golden dataset labels.

Limitation stated in the output: the golden dataset has only 5 judged items per run, so (3)
is indicative. Expanding the golden set (evaluation/golden_dataset/ANNOTATION_PROTOCOL.md)
is a precondition for a real calibration.

Usage: python -m evaluation.calibration [--gold v1.0|v1.1]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestration.state import InsurMindsState
from .aggregate_runs import a5_generation
from .golden_resolvers import exclusion_concept_keys
from .run_live_golden import A5_FIELD_ALIASES, EXPECTED_COMPARISON, GOLD_DIR, RESULTS_DIR

BANDS = ((0.0, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 1.01))
THRESHOLDS = (0.7, 0.8, 0.85, 0.9, 0.95)


def judged(state):
    """Items whose status came from the semantic judge (pairs present on both sides)."""
    return [x for x in state.comparison.fields
            if x.confidence is not None and x.policy_a.value is not None and x.policy_b.value is not None
            and (":" in x.field or x.field in ("retentions", "reporting_period"))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", default="v1.0", choices=list(EXPECTED_COMPARISON))
    args = parser.parse_args()
    expected = json.loads((GOLD_DIR / EXPECTED_COMPARISON[args.gold]).read_text(encoding="utf-8"))["comparisons"]
    confs, labelled = [], []
    runs = 0
    for f in sorted(RESULTS_DIR.glob("LIVE_GD01_GD02_*.json")):
        state = InsurMindsState.model_validate_json(f.read_text(encoding="utf-8"))
        if state.comparison is None or a5_generation(state) != "A5 v2 (taxonomia)":
            continue
        runs += 1
        items = judged(state)
        confs += [x.confidence for x in items]
        by_field = {x.field: x for x in state.comparison.fields}
        for e in expected:
            if e["expected_status"] == "NOT_IDENTIFIED":
                continue
            name = A5_FIELD_ALIASES.get(e["field"], e["field"])
            fields = [name] if name in by_field else exclusion_concept_keys(list(by_field), e["field"].split(".", 1)[1]) if e["field"].startswith("exclusion.") else []
            for k in fields:
                x = by_field[k]
                if x.confidence is not None and x.policy_a.value is not None and x.policy_b.value is not None:
                    labelled.append((x.confidence, x.status.value == e["expected_status"]))
    lines = [f"# Calibração do juiz semântico (A5) — {runs} run(s) LIVE com A5 v2, gabarito {args.gold}", ""]
    lines += [f"Itens julgados: {len(confs)} · confiança mínima observada: {min(confs):.2f} · mediana: {sorted(confs)[len(confs)//2]:.2f}", ""]
    lines += ["| Corte (A5_MIN_CONFIDENCE) | Itens enviados à revisão | % |", "|---|---|---|"]
    for t in THRESHOLDS:
        n = sum(c < t for c in confs)
        lines.append(f"| {t:.2f} | {n} | {100 * n / len(confs):.0f}% |")
    lines += ["", "| Faixa de confiança | Itens do gabarito | Acertos | Acurácia |", "|---|---|---|---|"]
    for lo, hi in BANDS:
        sel = [ok for c, ok in labelled if lo <= c < hi]
        if sel:
            lines.append(f"| [{lo:.2f}, {min(hi, 1):.2f}) | {len(sel)} | {sum(sel)} | {sum(sel) / len(sel):.2f} |")
    lines += ["", f"Limitação: {len(labelled)} itens rotulados no total. A acurácia por faixa é indicativa; "
              "a calibração real exige ampliar o gabarito (ANNOTATION_PROTOCOL.md)."]
    print("\n".join(lines))
    (RESULTS_DIR / f"CALIBRATION_{args.gold}.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
