from pathlib import Path
from llm.client import DeterministicLLMClient
from orchestration.state import InsurMindsState, RunStatus
from orchestration.intelligence_pipeline import IntelligencePipeline
from storage.database import Database


def state_with_text():
    return InsurMindsState(
        run_id='run-m3', status=RunStatus.EXTRACTING,
        documents=[{'document_id':'doc-1','filename':'policy.pdf','format':'PDF','source_path':'policy.pdf','size_bytes':123,'status':'VALID'}],
        raw_texts={'doc-1':'APÓLICE D&O. Seguradora Alfa. Limite R$ 10.000.000.'}
    )


def valid_response():
    return {'insurer':' Seguradora   Alfa ','policy_type':'D&O','currency':'brl','limit_of_liability':{'amount':'10000000','currency':'brl'},'coverages':[],'exclusions':[]}


def test_a3_injects_pipeline_identity(tmp_path):
    llm=DeterministicLLMClient([valid_response()]); p=IntelligencePipeline(llm,tmp_path/'m3.db')
    s=p.process(state_with_text())
    assert s.status == RunStatus.READY_TO_COMPARE
    assert s.validated_policies[0].document_id == 'doc-1'
    assert s.validated_policies[0].source_file == 'policy.pdf'
    assert s.validated_policies[0].insurer == 'Seguradora Alfa'
    assert s.validated_policies[0].currency == 'BRL'


def test_validated_policy_is_persisted(tmp_path):
    llm=DeterministicLLMClient([valid_response()]); dbp=tmp_path/'m3.db'; p=IntelligencePipeline(llm,dbp)
    s=p.process(state_with_text()); saved=Database(dbp).get_latest_policy('doc-1')
    assert saved['insurer'] == 'Seguradora Alfa'
    assert saved['limit_of_liability']['amount'] == '10000000'


def test_retry_then_success(tmp_path):
    bad={'currency':'BRL','coverages':[{'present':True}]} # missing coverage name
    llm=DeterministicLLMClient([bad, valid_response()]); p=IntelligencePipeline(llm,tmp_path/'m3.db',max_retries=2)
    s=p.process(state_with_text())
    assert s.status == RunStatus.READY_TO_COMPARE
    assert llm.calls == 2
    assert s.metrics['intelligence_attempts'] == 2
    assert any(w.startswith('A4: tentativa 1 rejeitada') for w in s.warnings)


def test_retry_exhaustion_requires_review(tmp_path):
    bad={'coverages':[{'present':True}]}
    llm=DeterministicLLMClient([bad]); p=IntelligencePipeline(llm,tmp_path/'m3.db',max_retries=2)
    s=p.process(state_with_text())
    assert s.status == RunStatus.REVIEW_REQUIRED
    assert llm.calls == 3
    assert s.metrics['intelligence_attempts'] == 3


def test_empty_text_fails_controlled(tmp_path):
    s=state_with_text(); s.raw_texts['doc-1']=''
    llm=DeterministicLLMClient([valid_response()]); p=IntelligencePipeline(llm,tmp_path/'m3.db')
    out=p.process(s)
    assert out.status == RunStatus.FAILED
    assert out.errors
