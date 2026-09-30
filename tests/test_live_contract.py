from pathlib import Path
import json
import pymupdf
from llm.client import DeterministicLLMClient, OpenAIStructuredLLMClient, StructuredOutputError
from llm.schema_contract import strict_policy_json_schema
from orchestration.mvp_pipeline import CompleteMVPPipeline
from orchestration.state import RunStatus
from schemas.policy import PolicySchema
from tools.pdf_tools import extract_pdf_text
from tools.text_budget import fit_to_budget, join_pages, split_pages


def make_pdf(path: Path, pages: list[str]):
    d = pymupdf.open()
    for text in pages:
        d.new_page().insert_text((72, 72), text)
    d.save(path); d.close()


def valid_response(number="A-1"):
    return {"policy_number": number, "insurer": "Alpha Seguros", "policy_type": "D&O", "currency": "BRL",
            "retentions": [], "insuring_agreements": [], "coverages": [], "sublimits": [], "exclusions": [],
            "clauses": [], "extensions": [], "source_references": [], "warnings": []}


# --- strict schema contract -------------------------------------------------

def _objects(node):
    if isinstance(node, dict):
        if "properties" in node:
            yield node
        for v in node.values():
            yield from _objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from _objects(v)


def test_strict_schema_closes_every_object_and_requires_all_properties():
    schema = strict_policy_json_schema(PolicySchema.model_json_schema())
    objects = list(_objects(schema))
    assert objects
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])


def test_strict_schema_excludes_pipeline_fields_and_unsupported_keywords():
    schema = strict_policy_json_schema(PolicySchema.model_json_schema())
    assert "document_id" not in schema["properties"]
    assert "source_file" not in schema["properties"]
    text = json.dumps(schema)
    for keyword in ('"default"', '"pattern"', '"minLength"'):
        assert keyword not in text
    # Property names that coincide with keywords must survive.
    assert "description" in schema["$defs"]["Coverage"]["properties"]


# --- OpenAI adapter (no network) ---------------------------------------------

class _FakeResponses:
    def __init__(self, output_text):
        self.output_text = output_text; self.requests = []
    def create(self, **request):
        self.requests.append(request)
        return type("R", (), {"output_text": self.output_text})()


def _adapter(output_text, max_input_chars=None):
    client = OpenAIStructuredLLMClient.__new__(OpenAIStructuredLLMClient)
    client.model = "test-model"
    client.max_input_chars = max_input_chars or OpenAIStructuredLLMClient.DEFAULT_MAX_INPUT_CHARS
    fake = _FakeResponses(output_text)
    client._client = type("C", (), {"responses": fake})()
    return client, fake


def test_adapter_sends_strict_schema_and_returns_unvalidated_candidate():
    client, fake = _adapter(json.dumps({"insurer": {"name": "X"}}))
    out = client.extract_policy(raw_text="[[PÁGINA 1]]\ntexto", document={"document_id": "d", "filename": "f.pdf"},
                                schema=PolicySchema.model_json_schema())
    fmt = fake.requests[0]["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    assert "document_id" not in fmt["schema"]["properties"]
    # Invalid shape is passed through: A4 is the validation authority.
    assert out == {"insurer": {"name": "X"}}


def test_adapter_invalid_json_is_retryable_error():
    client, _ = _adapter("not json")
    try:
        client.extract_policy(raw_text="x", document={}, schema=PolicySchema.model_json_schema())
    except StructuredOutputError:
        pass
    else:
        raise AssertionError("expected StructuredOutputError")


def test_adapter_sends_feedback_and_reports_omitted_pages():
    client, fake = _adapter(json.dumps(valid_response()), max_input_chars=60)
    raw = join_pages([{"page": i, "text": "x" * 30} for i in range(1, 6)])
    out = client.extract_policy(raw_text=raw, document={}, schema=PolicySchema.model_json_schema(),
                                feedback=["insurer: Input should be a valid string"])
    messages = fake.requests[0]["input"]
    assert "insurer: Input should be a valid string" in messages[-1]["content"]
    assert any("omitida" in w for w in out["warnings"])


# --- page markers and budget --------------------------------------------------

def test_pdf_text_has_page_markers(tmp_path):
    p = tmp_path / "p.pdf"; make_pdf(p, ["Primeira", "Segunda"])
    text = extract_pdf_text(p)["text"]
    assert "[[PÁGINA 1]]" in text and "[[PÁGINA 2]]" in text
    assert [x["page"] for x in split_pages(text)] == [1, 2]


def test_budget_keeps_first_pages_and_most_relevant_in_order():
    pages = [{"page": 1, "text": "capa"}, {"page": 2, "text": "irrelevante " * 5},
             {"page": 3, "text": "exclusão franquia cobertura"}, {"page": 4, "text": "nada " * 5}]
    text, omitted = fit_to_budget(join_pages(pages), max_chars=70, keep_first=1)
    assert len(text) <= 70
    assert "[[PÁGINA 1]]" in text and "[[PÁGINA 3]]" in text
    assert text.index("[[PÁGINA 1]]") < text.index("[[PÁGINA 3]]")
    assert omitted == [2, 4]


def test_budget_noop_when_text_fits():
    assert fit_to_budget("curto", 100) == ("curto", [])


# --- Harness retry with feedback ----------------------------------------------

def test_invalid_candidate_triggers_retry_with_feedback_then_completes(tmp_path):
    a = tmp_path / "a.pdf"; b = tmp_path / "b.pdf"
    make_pdf(a, ["A"]); make_pdf(b, ["B"])
    bad = dict(valid_response(), insurer={"name": "Alpha"})
    llm = DeterministicLLMClient([bad, valid_response("A-1"), valid_response("B-1")])
    state = CompleteMVPPipeline(llm, db_path=tmp_path / "r.db").process(a, b)
    assert state.status == RunStatus.COMPLETED
    assert llm.feedback_received[0] is None
    assert any("insurer" in line for line in llm.feedback_received[1])
    assert any(t.event == "POLICY_VALIDATION_FAILED" for t in state.trace)


def test_unparseable_output_exhausts_retries_to_review_required(tmp_path):
    class Broken:
        calls = 0
        def extract_policy(self, **kwargs):
            self.calls += 1
            raise StructuredOutputError("OpenAI returned invalid JSON")
    a = tmp_path / "a.pdf"; b = tmp_path / "b.pdf"
    make_pdf(a, ["A"]); make_pdf(b, ["B"])
    llm = Broken()
    state = CompleteMVPPipeline(llm, db_path=tmp_path / "r.db", max_retries=2).process(a, b)
    assert llm.calls == 3
    assert state.status == RunStatus.REVIEW_REQUIRED


# --- dates -----------------------------------------------------------------------

def test_a4_normalizes_brazilian_dates():
    from agents.validation_agent import ValidationAgent
    policy = ValidationAgent().process(dict(valid_response(), document_id="d", source_file="f.pdf",
                                            effective_date="01/10/2026", expiration_date="30/09/2027"))
    assert policy.effective_date.isoformat() == "2026-10-01"
    assert policy.expiration_date.isoformat() == "2027-09-30"


def test_a4_rejects_garbled_llm_dates():
    import pytest
    from agents.validation_agent import ValidationAgent, PolicyValidationError
    with pytest.raises(PolicyValidationError):
        ValidationAgent().process(dict(valid_response(), document_id="d", source_file="f.pdf",
                                       effective_date="0110-01-10"))


def test_a4_drops_role_definitions_from_individualized_fields():
    from agents.validation_agent import ValidationAgent
    policy = ValidationAgent().process(dict(valid_response(), document_id="d", source_file="f.pdf",
        insurer="Companhia de seguros definida no frontispício da Apólice",
        insured_entity="Sociedade identificada na Especificação da Apólice"))
    assert policy.insurer is None and policy.insured_entity is None
    assert sum("A4 guardrail" in w for w in policy.warnings) == 2
    kept = ValidationAgent().process(dict(valid_response(), document_id="d", source_file="f.pdf", insurer="SOMPO SEGUROS S.A."))
    assert kept.insurer == "SOMPO SEGUROS S.A."
