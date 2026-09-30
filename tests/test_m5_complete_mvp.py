from pathlib import Path
import fitz
from llm.client import DeterministicLLMClient
from orchestration.mvp_pipeline import CompleteMVPPipeline
from orchestration.state import RunStatus
from agents.synthesis_agent import SynthesisAgent

def make_pdf(path: Path, text: str):
    d=fitz.open(); p=d.new_page(); p.insert_text((72,72),text); d.save(path); d.close()

def response(number, insurer, insured, limit):
    return {
        "policy_number":number,"insurer":insurer,"insured_entity":insured,"policy_type":"D&O",
        "currency":"BRL","limit_of_liability":{"amount":limit,"currency":"BRL"},
        "aggregate_limit":None,"retentions":[],
        "insuring_agreements":[{"side":"A","present":True,"title":"Side A"}],
        "coverages":[],"sublimits":[],"exclusions":[],"clauses":[],"extensions":[],
        "source_references":[],"warnings":[]
    }

def test_a6_synthesizes_only_comparison():
    from schemas.comparison import ComparisonResult, FieldComparison, ComparedValue, ComparisonStatus
    c=ComparisonResult(run_id="r",policy_a_document_id="A",policy_b_document_id="B",
        fields=[FieldComparison(field="currency",policy_a=ComparedValue(value="BRL"),
          policy_b=ComparedValue(value="BRL"),status=ComparisonStatus.EQUAL,confidence=1.0)])
    report=SynthesisAgent().process(c)
    assert "Campos comparados: 1" in report
    assert "recomendação jurídica" in report

def test_complete_mvp_one_run_two_docs_a1_to_a6(tmp_path):
    a=tmp_path/"a.pdf"; b=tmp_path/"b.pdf"
    make_pdf(a,"Policy A test document")
    make_pdf(b,"Policy B test document")
    llm=DeterministicLLMClient([
        response("A-1","Alpha Seguros","Empresa X","10000000"),
        response("B-1","Beta Seguros","Empresa X","15000000"),
    ])
    state=CompleteMVPPipeline(llm,db_path=tmp_path/"mvp.db").process(a,b)
    assert state.status == RunStatus.COMPLETED
    assert len(state.documents)==2
    assert len(state.validated_policies)==2
    assert state.comparison is not None
    assert state.final_report
    agents={x.agent for x in state.trace}
    for expected in {"A1_INTAKE","A2_EXTRACTION","A3_D&O_ANALYSIS","A4_VALIDATION","A5_COMPARISON","A6_SYNTHESIS"}:
        assert expected in agents

def test_report_persisted(tmp_path):
    a=tmp_path/"a.pdf"; b=tmp_path/"b.pdf"
    make_pdf(a,"A"); make_pdf(b,"B")
    llm=DeterministicLLMClient([response("A","X","Y","1"),response("B","X","Y","2")])
    pipe=CompleteMVPPipeline(llm,db_path=tmp_path/"mvp.db")
    state=pipe.process(a,b)
    assert pipe.db.get_latest_report(state.run_id) == state.final_report

def test_streamlit_app_compiles():
    app=Path(__file__).parents[1]/"app.py"
    compile(app.read_text(encoding="utf-8"),str(app),"exec")
