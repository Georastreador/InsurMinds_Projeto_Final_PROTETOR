import json
from pathlib import Path
from evaluation.models import GoldenPolicyAnnotation
from evaluation.evaluator import QualityEvaluator
from observability.quality_report import ObservabilityReport
from schemas.policy import PolicySchema, Money, SourceReference
from schemas.comparison import ComparisonResult, FieldComparison, ComparedValue, ComparisonStatus

def gold():
    return GoldenPolicyAnnotation(document_id="d1",source_file="x.pdf",policy_type="D&O",annotations=[
        {"field":"policy_number","expected":"DO-001","source_page":1,"source_excerpt":"Apólice DO-001"},
        {"field":"currency","expected":"BRL","source_page":1,"source_excerpt":"BRL"}
    ])

def policy():
    return PolicySchema(document_id="d1",source_file="x.pdf",policy_number="DO-001",currency="BRL",
                  source_references=[SourceReference(page=1,excerpt="Apólice DO-001; moeda BRL")])

def test_eval01_schema_validity():
    r=QualityEvaluator().eval_01_schema_validity(policy())
    assert r.passed and r.score==1

def test_eval02_extraction_against_gold():
    r=QualityEvaluator().eval_02_field_extraction(policy(),gold())
    assert r.passed and r.score==1

def test_eval03_claim_evidence():
    r=QualityEvaluator().eval_03_evidence_grounding(policy(),gold())
    assert r.passed and r.score==1

def test_eval04_comparison_accuracy():
    c=ComparisonResult(run_id="r",policy_a_document_id="A",policy_b_document_id="B",fields=[
        FieldComparison(field="currency",policy_a=ComparedValue(value="BRL"),policy_b=ComparedValue(value="BRL"),
                        status=ComparisonStatus.EQUAL,confidence=1.0)
    ])
    r=QualityEvaluator().eval_04_comparison_accuracy(c,{"currency":"EQUAL"})
    assert r.passed and r.score==1

def test_eval05_is_explicit_proxy():
    r=QualityEvaluator().eval_05_unsupported_claim_proxy(policy(),"Apólice DO-001 moeda BRL")
    assert r.passed
    assert any("Lexical proxy" in x for x in r.limitations)

def test_quality_report_aggregates_without_agent():
    ev=QualityEvaluator()
    report=ObservabilityReport().build_quality_report([ev.eval_01_schema_validity(policy())])
    assert report["all_passed"] is True
    assert "methodological_note" in report
