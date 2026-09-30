"""Scope guardrail (line of business) and verification layer 2: offline robustness
over the Test/Stress Dataset. Stress cases are skipped when the dataset is absent."""
from pathlib import Path
import pytest
from schemas.policy import PolicySchema
from schemas.comparison import ComparisonStatus
from schemas.do_taxonomy import LineOfBusiness
from agents.comparison_agent import ComparisonAgent
from orchestration.scope import GENERIC, VALIDATED, assess_scope
from llm.client import DemoHeuristicLLMClient
from orchestration.mvp_pipeline import CompleteMVPPipeline
from orchestration.state import RunStatus
from tools.pdf_tools import extract_pdf_text
from tools.text_budget import fit_to_budget

ROOT = Path(__file__).resolve().parents[1]
STRESS = ROOT / "datasets" / "stress_test"
GOLD_PDFS = ROOT / "data" / "golden_dataset"

EXPECTED_LINES = {
    "01_susep_auto_condicoes_gerais.pdf": "auto",
    "02_bb_residencial_condicoes_gerais.pdf": "residencial",
    "03_porto_viagem_condicoes_gerais.pdf": "viagem",
    "04_chubb_empresarial_pme_condicoes_gerais.pdf": "empresarial",
    "05_banrisul_vida_digital_condicoes_contratuais.pdf": "vida",
    "06_apolice_seguro_garantia_publica.pdf": "garantia",
}


def pol(doc, line=None):
    return PolicySchema(document_id=doc, source_file=f"{doc}.pdf", line_of_business=line)


def test_scope_all_do_is_validated():
    scope, warnings = assess_scope([pol("a", LineOfBusiness.DO), pol("b", LineOfBusiness.DO)])
    assert scope["scope"] == VALIDATED and warnings == []


def test_scope_other_lines_are_generic_and_warned():
    scope, warnings = assess_scope([pol("a", LineOfBusiness.AUTO), pol("b", LineOfBusiness.RESIDENCIAL)])
    assert scope["scope"] == GENERIC
    assert any("Automóvel" in w for w in warnings) and any("ramos diferentes" in w for w in warnings)


def test_sides_not_applicable_outside_do():
    r = ComparisonAgent().compare("r", pol("a", LineOfBusiness.AUTO), pol("b", LineOfBusiness.AUTO))
    sides = [x for x in r.fields if x.field.startswith("insuring_side_")]
    assert sides and all(x.status == ComparisonStatus.NOT_APPLICABLE for x in sides)


def _stress_files():
    return sorted((STRESS / "pdfs").glob("*.pdf")) + [STRESS / "synthetic_apolice_residencial.pdf"]


needs_stress = pytest.mark.skipif(not (STRESS / "pdfs").exists(), reason="Test/Stress Dataset ausente")


@needs_stress
@pytest.mark.parametrize("name,line", sorted(EXPECTED_LINES.items()))
def test_demo_detects_line_of_business(name, line):
    text = extract_pdf_text(STRESS / "pdfs" / name)["text"]
    out = DemoHeuristicLLMClient().extract_policy(raw_text=text, document={}, schema={})
    assert out["line_of_business"] == line


@needs_stress
def test_demo_pipeline_never_fails_on_stress_pairs(tmp_path):
    files = _stress_files()
    for a, b in zip(files, files[1:] + files[:1]):
        state = CompleteMVPPipeline(DemoHeuristicLLMClient(), db_path=tmp_path / "s.db").process(a, b)
        assert state.status == RunStatus.COMPLETED, (a.name, b.name, state.errors)
        assert state.metrics["scope"] == GENERIC
        assert any("validada apenas para D&O" in w for w in state.warnings)


@needs_stress
def test_large_document_is_budgeted_with_disclosed_omissions():
    text = extract_pdf_text(STRESS / "pdfs" / "04_chubb_empresarial_pme_condicoes_gerais.pdf")["text"]
    kept, omitted = fit_to_budget(text, 300_000)
    assert len(kept) <= 300_000 and len(omitted) > 100
    assert "[[PÁGINA 1]]" in kept


@pytest.mark.skipif(not GOLD_PDFS.exists(), reason="PDFs do Golden Dataset ausentes")
def test_demo_detects_do_in_golden_pdfs():
    for f in GOLD_PDFS.glob("*.pdf"):
        out = DemoHeuristicLLMClient().extract_policy(raw_text=extract_pdf_text(f)["text"], document={}, schema={})
        assert out["line_of_business"] == "d_o", f.name


def test_detector_resolves_lines_left_open_by_llm():
    from orchestration.scope import reconcile_line_of_business
    text = "SEGURO RESIDENCIAL. Condições Gerais do seguro residencial para residência habitual. " * 3
    p = pol("a", LineOfBusiness.OUTRO)
    assert reconcile_line_of_business(p, text) and p.line_of_business == LineOfBusiness.RESIDENCIAL
    assert "detector determinístico" in p.warnings[-1]
    kept = pol("b", LineOfBusiness.VIDA)
    assert reconcile_line_of_business(kept, text) is None and kept.line_of_business == LineOfBusiness.VIDA
