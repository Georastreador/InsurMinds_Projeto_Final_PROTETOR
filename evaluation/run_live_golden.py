"""End-to-end Golden Dataset evaluation (GD01 Chubb x GD02 Sompo) on a real run.

Usage:
    python -m evaluation.run_live_golden --live            # runs A1->A6 in LIVE GPT, then evaluates
    python -m evaluation.run_live_golden --run-json PATH   # evaluates a saved run (no API cost)

Policy A must be GD01 (Chubb) and policy B GD02 (Sompo). Results are written to
evaluation/results/. See golden_resolvers.py for the annotation mapping rules.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from orchestration.state import InsurMindsState
from .evaluator import QualityEvaluator, _norm
from .golden_resolvers import OUT_OF_SCHEMA, _fold, exclusion_concept_keys, resolve
from .models import EvalResult, GoldenPolicyAnnotation

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "evaluation" / "golden_dataset"
RESULTS_DIR = ROOT / "evaluation" / "results"
PDF_A = ROOT / "data" / "golden_dataset" / "capital-fechado-processo-susep-15414-900832-2017-90-versao-a-partir-de-16-12-2025.pdf"
PDF_B = ROOT / "data" / "golden_dataset" / "CG RCD&O_28112025 -71 v1.5.pdf"


def load_gold(name: str) -> GoldenPolicyAnnotation:
    return GoldenPolicyAnnotation.model_validate_json((GOLD_DIR / name).read_text(encoding="utf-8"))


def eval_02(policy, gold) -> EvalResult:
    rows, gaps = [], []
    for ann in gold.annotations:
        actual, _ = resolve(policy, ann.field)
        if actual == OUT_OF_SCHEMA:
            gaps.append(ann.field); continue
        rows.append({"field": ann.field, "expected": ann.expected, "actual": actual,
                     "correct": _norm(actual) == _norm(ann.expected)})
    correct = sum(r["correct"] for r in rows)
    score = correct / len(rows) if rows else 0.0
    # v1.3: separate "must stay empty" fields (a null-returning extractor already gets them right)
    # from the fields that require extracting something.
    disc = [r for r in rows if r["expected"] not in (None, "", [], {})]
    return EvalResult(eval_id="EVAL-02", name=f"Field extraction accuracy ({gold.document_id})", score=score,
                      passed=bool(rows) and score >= 0.80, numerator=correct, denominator=len(rows),
                      details={"fields": rows, "out_of_schema_fields": gaps,
                               "discriminant": {"correct": sum(r["correct"] for r in disc), "total": len(disc),
                                                "score": (sum(r["correct"] for r in disc) / len(disc)) if disc else None},
                               "null_baseline": {"correct": len(rows) - len(disc), "total": len(rows),
                                                 "score": ((len(rows) - len(disc)) / len(rows)) if rows else None}},
                      limitations=["Concept annotations are mapped by the deterministic rules in golden_resolvers.py.",
                                   "OUT_OF_SCHEMA annotations are excluded from the denominator and require human review."])


def eval_03(policy, gold, raw_text: str = "") -> EvalResult:
    rows = []
    for ann in gold.annotations:
        if ann.expected in (None, "", [], {}):
            continue
        actual, refs = resolve(policy, ann.field)
        if actual == OUT_OF_SCHEMA:
            continue
        gold_excerpt = _fold(ann.source_excerpt)
        page_match = any(r.page == ann.source_page for r in refs)
        excerpt_match = any(
            gold_excerpt and r.excerpt and len(_fold(r.excerpt)) >= 15
            and (gold_excerpt in _fold(r.excerpt) or _fold(r.excerpt) in gold_excerpt)
            for r in refs)
        rows.append({"field": ann.field, "gold_page": ann.source_page,
                     "cited_pages": sorted({r.page for r in refs if r.page}),
                     "page_match": page_match, "excerpt_match": excerpt_match})
    grounded = sum(r["page_match"] for r in rows)
    score = grounded / len(rows) if rows else 0.0
    # v1.3: runtime verification of every evidence excerpt against its cited page (all references, not only gold fields).
    runtime = None
    if raw_text:
        from tools.evidence_check import verify_policy
        from tools.text_budget import split_pages
        runtime = {k: v for k, v in verify_policy(policy.model_copy(deep=True), split_pages(raw_text)).items() if k != "wrong_page_examples"}
    return EvalResult(eval_id="EVAL-03", name=f"Evidence grounding ({gold.document_id})", score=score,
                      passed=bool(rows) and score >= 0.80, numerator=grounded, denominator=len(rows),
                      details={"fields": rows, "excerpt_match_rate": (sum(r["excerpt_match"] for r in rows) / len(rows)) if rows else 0.0,
                               "runtime_evidence_check": runtime},
                      limitations=["Primary criterion: the evidence attached to the extracted fact cites the page cited by the human annotator.",
                                   "Secondary (details.excerpt_match_rate): verbatim overlap with the annotated excerpt."])


# Golden Dataset field -> A5 field, when the names differ.
A5_FIELD_ALIASES = {"retention_rule": "retentions"}


EXPECTED_COMPARISON = {"v1.0": "GD01_GD02_expected_comparison.json", "v1.1": "GD01_GD02_expected_comparison_v1.1.json"}


def eval_04(state: InsurMindsState, gold_version: str = "v1.1") -> EvalResult:
    expected = json.loads((GOLD_DIR / EXPECTED_COMPARISON[gold_version]).read_text(encoding="utf-8"))
    by_field = {x.field: x.status.value for x in state.comparison.fields}
    rows = []
    for item in expected["comparisons"]:
        field, exp = item["field"], item["expected_status"]
        a5_name = A5_FIELD_ALIASES.get(field, field)
        if a5_name in by_field:
            actual, a5_fields = by_field[a5_name], [a5_name]
        elif field.startswith("exclusion."):
            a5_fields = exclusion_concept_keys(list(by_field), field.split(".", 1)[1])
            statuses = sorted({by_field[f] for f in a5_fields})
            if not statuses:
                actual = "NOT_PRODUCED"
            elif statuses == ["ONLY_A", "ONLY_B"]:
                actual = "UNPAIRED(ONLY_A+ONLY_B)"
            else:
                actual = "+".join(statuses)
        else:
            actual, a5_fields = "NOT_PRODUCED", []
        rows.append({"field": field, "expected": exp, "actual": actual, "a5_fields": a5_fields, "correct": actual == exp})
    correct = sum(r["correct"] for r in rows)
    score = correct / len(rows)
    disc = [r for r in rows if r["expected"] != "NOT_IDENTIFIED"]
    return EvalResult(eval_id="EVAL-04", name=f"Comparison accuracy (end-to-end LIVE, gabarito {gold_version})", score=score,
                      passed=score >= 0.90, numerator=correct, denominator=len(rows),
                      details={"fields": rows,
                               "discriminant": {"correct": sum(r["correct"] for r in disc), "total": len(disc),
                                                "score": sum(r["correct"] for r in disc) / len(disc) if disc else None}},
                      limitations=["Measured on A5 output from a real LIVE run, not on curated representations."])


def evaluate(state: InsurMindsState) -> dict:
    pa, pb = state.validated_policies
    ga, gb = load_gold("GD01_CHUBB_ground_truth.json"), load_gold("GD02_SOMPO_ground_truth.json")
    ev = QualityEvaluator()
    results = [
        ev.eval_01_schema_validity(pa), ev.eval_01_schema_validity(pb),
        eval_02(pa, ga), eval_02(pb, gb),
        eval_03(pa, ga, state.raw_texts.get(pa.document_id, "")), eval_03(pb, gb, state.raw_texts.get(pb.document_id, "")),
        eval_04(state, "v1.0"),
        eval_04(state, "v1.1"),
        ev.eval_05_unsupported_claim_proxy(pa, state.raw_texts[pa.document_id]),
        ev.eval_05_unsupported_claim_proxy(pb, state.raw_texts[pb.document_id]),
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": state.run_id,
        "run_status": state.status.value,
        "model": state.metrics.get("llm_model"),
        "evaluations": [r.model_dump(mode="json") for r in results],
        "methodological_note": ("End-to-end LIVE evaluation on public D&O general conditions (Chubb, Sompo) "
                                "against human annotations. EVAL-05 is a lexical proxy."),
    }


def run_live() -> InsurMindsState:
    import os
    from dotenv import load_dotenv
    from llm.factory import build_live_components
    from orchestration.mvp_pipeline import CompleteMVPPipeline
    load_dotenv(ROOT / ".env")
    c = build_live_components()
    state = CompleteMVPPipeline(c.llm, semantic=c.semantic, writer=c.writer, ocr=c.ocr, guard=c.guard,
                                db_path=str(ROOT / "data" / "insurminds_protetor.db")).process(PDF_A, PDF_B)
    state.metrics["llm_model"] = os.getenv("OPENAI_MODEL")
    state.metrics["extraction_mode"] = c.extraction_mode
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--live", action="store_true")
    group.add_argument("--run-json", type=Path)
    args = parser.parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.live:
        state = run_live()
        (RESULTS_DIR / f"LIVE_GD01_GD02_{stamp}.json").write_text(state.model_dump_json(indent=1), encoding="utf-8")
    else:
        state = InsurMindsState.model_validate_json(args.run_json.read_text(encoding="utf-8"))
    if len(state.validated_policies) != 2 or state.comparison is None:
        raise SystemExit(f"Run {state.run_id} is not evaluable (status {state.status.value}).")
    report = evaluate(state)
    out = RESULTS_DIR / f"EVAL_GD01_GD02_{stamp}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    for r in report["evaluations"]:
        flag = "PASS" if r["passed"] else "FAIL"
        print(f"{r['eval_id']:8} {flag}  {r['score']:.2f}  ({r['numerator']}/{r['denominator']})  {r['name']}")
    print(f"\nRelatório: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
