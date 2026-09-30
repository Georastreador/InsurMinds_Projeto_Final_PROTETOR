import json
from agents.synthesis_agent import SynthesisAgent
from llm.client import OpenAISynthesisWriter
from schemas.comparison import ComparisonResult, ComparedValue, ComparisonStatus, FieldComparison
from schemas.policy import SourceReference


def item(field, status, a="x", b="y", pa=3, pb=7):
    return FieldComparison(field=field, status=status,
                           policy_a=ComparedValue(value=a, source=SourceReference(page=pa) if pa else None),
                           policy_b=ComparedValue(value=b, source=SourceReference(page=pb) if pb else None))


def comparison(n_extra=0):
    fields = [item("retentions", ComparisonStatus.DIFFERENT, {"conditions": "Franquia na Especificação"}, {"conditions": "Sem franquia na Cobertura A"}),
              item("exclusions:cibernetico", ComparisonStatus.REVIEW_REQUIRED),
              item("currency", ComparisonStatus.EQUAL, "BRL", "BRL")]
    fields += [item(f"coverages:extra {i}", ComparisonStatus.ONLY_A, {"name": f"Extra {i}", "description": "d" * 400}, None) for i in range(n_extra)]
    return ComparisonResult(run_id="r", policy_a_document_id="A", policy_b_document_id="B", fields=fields)


class Writer:
    model = "fake"
    def __init__(self, draft=None, error=None): self.draft, self.error, self.payload = draft, error, None
    def write(self, payload):
        self.payload = payload
        if self.error: raise self.error
        return self.draft


def test_generative_draft_is_bounded_to_a5_items_with_pages_attached():
    writer = Writer({"overview": "As franquias diferem.",
                     "key_differences": [{"id": "retentions", "summary": "A remete à Especificação; B dispensa franquia na Cobertura A."},
                                         {"id": "inventado", "summary": "Item que não existe."}],
                     "review_points": [{"id": "exclusions:cibernetico", "summary": "Escopos distintos."}]})
    agent = SynthesisAgent(writer)
    report = agent.process(comparison(), {"name_a": "Chubb", "name_b": "Sompo"})
    assert agent.last_method == "generative (fake)"
    assert "Chubb × Sompo" in report and "Franquias / retenções" in report
    assert "A p. 3 · B p. 7" in report
    assert "inventado" not in report and "Item que não existe" not in report
    assert "Riscos cibernéticos" in report
    assert {i["id"] for i in writer.payload["items"]} == {"retentions", "exclusions:cibernetico"}


def test_verdict_language_discards_draft():
    writer = Writer({"overview": "A apólice A é melhor.", "key_differences": [], "review_points": []})
    agent = SynthesisAgent(writer)
    report = agent.process(comparison())
    assert agent.last_method == "deterministic" and "veredito" in agent.last_warning
    assert "é melhor" not in report


def test_writer_failure_falls_back_without_failing():
    agent = SynthesisAgent(Writer(error=RuntimeError("down")))
    report = agent.process(comparison())
    assert agent.last_method == "deterministic" and "RuntimeError" in agent.last_warning
    assert "## Principais diferenças" in report


def test_fallback_is_compact_and_prioritized():
    report = SynthesisAgent().process(comparison(n_extra=70))
    assert len(report) < 6000
    assert report.index("Franquias / retenções") < report.index("Cobertura: Extra 0")
    assert "lista completa de 72 itens" in report


def test_openai_writer_uses_strict_schema():
    class Responses:
        def create(self, **req):
            assert req["text"]["format"]["strict"] is True
            return type("R", (), {"output_text": json.dumps({"overview": "o", "key_differences": [], "review_points": []})})()
    writer = OpenAISynthesisWriter(model="m", client=type("C", (), {"responses": Responses()})())
    assert writer.write({"items": []})["overview"] == "o"


def test_verdict_guardrail_ignores_punctuation_and_accents():
    from agents.synthesis_agent import has_verdict
    assert has_verdict("A apólice A é melhor.") and has_verdict("Opção RECOMENDADA, sem dúvida")
    assert not has_verdict("Cobertura de melhoria contínua") and not has_verdict("")
