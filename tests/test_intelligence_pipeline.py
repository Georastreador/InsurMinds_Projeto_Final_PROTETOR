"""A3/A4 behaviour inside the Harness (formerly tested on the removed IntelligencePipeline)."""
from pathlib import Path
import pymupdf
from llm.client import DeterministicLLMClient
from orchestration.mvp_pipeline import CompleteMVPPipeline
from orchestration.orchestrator import ALLOWED_TRANSITIONS
from orchestration.state import RunStatus
from storage.database import Database


def pdfs(tmp_path, a_text='APÓLICE D&O. Seguradora Alfa. Limite R$ 10.000.000.', b_text='APÓLICE D&O B.'):
    a, b = tmp_path / 'policy.pdf', tmp_path / 'b.pdf'
    for path, text in ((a, a_text), (b, b_text)):
        d = pymupdf.open(); d.new_page().insert_text((72, 72), text); d.save(path); d.close()
    return a, b


def valid_response():
    return {'insurer': ' Seguradora   Alfa ', 'policy_type': 'D&O', 'currency': 'brl',
            'limit_of_liability': {'amount': '10000000', 'currency': 'brl'}, 'coverages': [], 'exclusions': []}


def run(tmp_path, responses, **kw):
    llm = DeterministicLLMClient(responses)
    a, b = pdfs(tmp_path)
    pipe = CompleteMVPPipeline(llm, db_path=tmp_path / 'm3.db', **kw)
    return pipe.process(a, b), llm, pipe


def assert_valid_state_history(state):
    """Every recorded state change is an allowed transition (no bypass of the Orchestrator)."""
    changes = [e.event for e in state.trace if e.event.startswith('STATE_')]
    assert changes
    for ev in changes:
        body = ev[len('STATE_'):]
        pairs = [(o, body[len(o.value) + 4:]) for o in RunStatus if body.startswith(o.value + '_TO_')]
        old, new = next((o, RunStatus(n)) for o, n in pairs if n in RunStatus._value2member_map_)
        assert new in ALLOWED_TRANSITIONS[old], ev


def test_a3_injects_pipeline_identity_and_a4_normalizes(tmp_path):
    s, _, _ = run(tmp_path, [valid_response()])
    assert s.status == RunStatus.COMPLETED
    pol = s.validated_policies[0]
    assert pol.document_id == s.documents[0]['document_id'] and pol.source_file == 'policy.pdf'
    assert pol.insurer == 'Seguradora Alfa' and pol.currency == 'BRL'
    assert_valid_state_history(s)


def test_validated_policy_is_persisted(tmp_path):
    s, _, _ = run(tmp_path, [valid_response()])
    saved = Database(tmp_path / 'm3.db').get_latest_policy(s.documents[0]['document_id'])
    assert saved['insurer'] == 'Seguradora Alfa' and saved['limit_of_liability']['amount'] == '10000000'


def test_retry_then_success(tmp_path):
    bad = {'currency': 'BRL', 'coverages': [{'present': True}]}  # missing coverage name
    s, llm, _ = run(tmp_path, [bad, valid_response()], max_retries=2)
    assert s.status == RunStatus.COMPLETED
    assert llm.calls == 3  # A: bad + good, B: good
    assert s.metrics['a3_attempts'] == {'Documento A': 2, 'Documento B': 1}
    assert any(w.startswith('A4: tentativa 1 rejeitada') for w in s.warnings)
    assert 'STATE_VALIDATING_TO_RETRYING' in {e.event for e in s.trace}
    assert_valid_state_history(s)


def test_retry_exhaustion_requires_review(tmp_path):
    s, llm, _ = run(tmp_path, [{'coverages': [{'present': True}]}], max_retries=2)
    assert s.status == RunStatus.REVIEW_REQUIRED
    assert llm.calls == 3
    assert_valid_state_history(s)


def test_empty_text_fails_controlled(tmp_path):
    a, b = tmp_path / 'empty.pdf', tmp_path / 'b.pdf'
    d = pymupdf.open(); d.new_page(); d.save(a); d.close()
    d = pymupdf.open(); d.new_page().insert_text((72, 72), 'B'); d.save(b); d.close()
    s = CompleteMVPPipeline(DeterministicLLMClient([valid_response()]), db_path=tmp_path / 'x.db').process(a, b)
    assert s.status == RunStatus.FAILED and s.errors
