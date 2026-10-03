"""Multi-run evaluation: mean, worst case and spread over every saved LIVE golden run.

v1.2 reported the best run (EVAL-04 = 0.80 / 1.00). This script re-evaluates every saved
`LIVE_GD01_GD02_*.json` with the current evaluator (offline, no API cost) and reports, per
metric: mean, min (worst case), max and standard deviation, plus the discriminant
subscores (fields/items whose expected value is not "empty / not identified").

Runs are grouped by A5 generation, detected from the comparison output:
- "A5 v2 (taxonomia)": comparison keys use the D&O taxonomy (e.g. exclusions:poluicao_ambiental);
- "A5 v1 (nomes do LLM)": earlier code, kept only for the evolution history.

Usage:
    python -m evaluation.aggregate_runs                  # all saved runs
    python -m evaluation.aggregate_runs --runs a.json b.json
Writes evaluation/results/AGGREGATE_<stamp>.json and .md.
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path

from orchestration.state import InsurMindsState
from schemas.do_taxonomy import ClauseCategory, CoverageCategory, ExclusionCategory
from .run_live_golden import RESULTS_DIR, evaluate

TAXONOMY_KEYS = {c.value for e in (ExclusionCategory, CoverageCategory, ClauseCategory) for c in e} - {"outra"}


def a5_generation(state: InsurMindsState) -> str:
    keys = [f.field.split(":", 1)[1] for f in state.comparison.fields if ":" in f.field]
    hits = sum(k in TAXONOMY_KEYS for k in keys)
    return "A5 v2 (taxonomia)" if keys and hits / len(keys) >= 0.3 else "A5 v1 (nomes do LLM)"


def per_run_metrics(report: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for e in report["evaluations"]:
        name = e["name"]
        doc = "Chubb" if "CHUBB" in name else "Sompo" if "SOMPO" in name else None
        if e["eval_id"] == "EVAL-02":
            out[f"EVAL-02 {doc} (todos)"] = e["score"]
            d = e["details"].get("discriminant") or {}
            if d.get("score") is not None:
                out[f"EVAL-02 {doc} (discriminantes)"] = d["score"]
            nb = e["details"].get("null_baseline") or {}
            if nb.get("score") is not None:
                out[f"EVAL-02 {doc} (baseline que só devolve nulos)"] = nb["score"]
        elif e["eval_id"] == "EVAL-03":
            out[f"EVAL-03 {doc} (página)"] = e["score"]
            out[f"EVAL-03 {doc} (trecho = gabarito)"] = e["details"].get("excerpt_match_rate") or 0.0
            rt = e["details"].get("runtime_evidence_check") or {}
            if rt.get("verified_rate") is not None:
                out[f"Evidência conferida na página {doc} (todas as refs)"] = rt["verified_rate"]
        elif e["eval_id"] == "EVAL-04":
            version = "v1.1" if "v1.1" in name else "v1.0"
            out[f"EVAL-04 {version} (10 itens)"] = e["score"]
            d = e["details"].get("discriminant") or {}
            if d.get("score") is not None:
                out[f"EVAL-04 {version} (discriminantes)"] = d["score"]
    return out


def summarize(values: list[float]) -> dict[str, float]:
    return {"n": len(values), "mean": round(statistics.mean(values), 3), "min": round(min(values), 3),
            "max": round(max(values), 3), "stdev": round(statistics.pstdev(values), 3)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="*", type=Path)
    args = parser.parse_args()
    files = args.runs or sorted(RESULTS_DIR.glob("LIVE_GD01_GD02_*.json"))
    runs = []
    for f in files:
        state = InsurMindsState.model_validate_json(f.read_text(encoding="utf-8"))
        if len(state.validated_policies) != 2 or state.comparison is None:
            continue
        report = evaluate(state)
        runs.append({"file": f.name, "run_id": state.run_id, "generation": a5_generation(state),
                     "comparison_fields": len(state.comparison.fields),
                     "review_required": sum(1 for x in state.comparison.fields if x.review_required),
                     "metrics": per_run_metrics(report)})
    groups: dict[str, dict] = {}
    for gen in sorted({r["generation"] for r in runs}, reverse=True):
        members = [r for r in runs if r["generation"] == gen]
        names = sorted({k for r in members for k in r["metrics"]})
        groups[gen] = {"runs": [r["file"] for r in members],
                       "metrics": {k: summarize([r["metrics"][k] for r in members if k in r["metrics"]]) for k in names}}
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = {"generated_at": datetime.now().isoformat(), "runs": runs, "groups": groups,
           "note": "Re-avaliação offline dos runs LIVE gravados com o avaliador atual. Reportar média e pior caso, não o melhor run."}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"AGGREGATE_{stamp}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# Avaliação agregada — {len(runs)} runs LIVE (GD01 Chubb × GD02 Sompo)", ""]
    for gen, g in groups.items():
        lines += [f"## {gen} — {len(g['runs'])} run(s)", "", "| Métrica | Média | Pior | Melhor | Desvio |", "|---|---|---|---|---|"]
        for k, v in g["metrics"].items():
            lines.append(f"| {k} | {v['mean']:.2f} | {v['min']:.2f} | {v['max']:.2f} | {v['stdev']:.2f} |")
        lines += ["", "Runs: " + ", ".join(g["runs"]), ""]
    (RESULTS_DIR / f"AGGREGATE_{stamp}.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
