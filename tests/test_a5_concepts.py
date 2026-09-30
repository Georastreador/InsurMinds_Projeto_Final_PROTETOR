import json
from schemas.policy import PolicySchema
from schemas.comparison import ComparisonStatus
from schemas.do_taxonomy import ExclusionCategory, categorize, canonical_territorial_scope
from agents.comparison_agent import ComparisonAgent
from llm.client import OpenAISemanticComparator


def pol(doc, **kw):
    return PolicySchema.model_validate({"document_id": doc, "source_file": f"{doc}.pdf", **kw})


def field(r, name):
    return next(x for x in r.fields if x.field == name)


class Judge:
    def __init__(self, status="EQUAL", confidence=0.95, reason="Mesmo escopo."):
        self.result = {"status": status, "confidence": confidence, "reason": reason}; self.requests = []
    def compare_many(self, requests):
        self.requests.extend(requests); return [dict(self.result) for _ in requests]


def test_items_in_different_languages_pair_by_concept():
    a = pol("A", exclusions=[{"name": "Cyber risks", "normalized_name": "cyber_risks_and_data_loss"}])
    b = pol("B", exclusions=[{"name": "Responsabilidade cibernética", "normalized_name": "riscos cibernéticos"}])
    judge = Judge()
    r = ComparisonAgent(judge).compare("r", a, b)
    assert field(r, "exclusions:cibernetico").status == ComparisonStatus.EQUAL
    assert len(judge.requests) == 1
    assert not [x for x in r.fields if x.field.startswith("exclusions:") and x.field != "exclusions:cibernetico"]


def test_declared_category_takes_precedence_over_keywords():
    a = pol("A", exclusions=[{"name": "Item X", "category": "poluicao_ambiental"}])
    assert categorize(ExclusionCategory, a.exclusions[0]) == ExclusionCategory.POLUICAO_AMBIENTAL


def test_several_items_of_one_concept_are_judged_together():
    a = pol("A", exclusions=[{"name": "Environmental damage"}, {"name": "Environmental cleanup"}])
    b = pol("B", exclusions=[{"name": "Poluição"}])
    judge = Judge()
    r = ComparisonAgent(judge).compare("r", a, b)
    x = field(r, "exclusions:poluicao_ambiental")
    assert isinstance(x.policy_a.value, list) and len(x.policy_a.value) == 2
    assert len(judge.requests) == 1


def test_concept_fields_compare_meaning_not_wording():
    a = pol("A", policy_type="Seguro de RC de Diretores e Administradores (D&O) – Capital Fechado",
            territorial_scope="Qualquer parte do mundo, salvo indicação diversa na Especificação")
    b = pol("B", policy_type="Seguro de RC para Conselheiros, Diretores e/ou Administradores (D&O)",
            territorial_scope="Qualquer lugar do mundo, salvo disposição diversa na Especificação.")
    r = ComparisonAgent().compare("r", a, b)
    assert field(r, "policy_type").status == ComparisonStatus.EQUAL
    assert field(r, "territorial_scope").status == ComparisonStatus.EQUAL
    assert canonical_territorial_scope("Brasil") == "brasil"


def test_retentions_are_compared():
    a = pol("A", retentions=[{"conditions": "Franquia conforme Especificação"}])
    b = pol("B", retentions=[{"conditions": "Não se aplica franquia na Cobertura A"}])
    r = ComparisonAgent(Judge("DIFFERENT")).compare("r", a, b)
    assert field(r, "retentions").status == ComparisonStatus.DIFFERENT
    assert field(r, "reporting_period").status == ComparisonStatus.NOT_IDENTIFIED


def test_semantic_guardrails_escalate_to_review():
    a = pol("A", exclusions=[{"name": "Poluição"}]); b = pol("B", exclusions=[{"name": "Pollution"}])
    low = ComparisonAgent(Judge("EQUAL", confidence=0.4)).compare("r", a, b)
    assert field(low, "exclusions:poluicao_ambiental").status == ComparisonStatus.REVIEW_REQUIRED
    verdict = ComparisonAgent(Judge("DIFFERENT", reason="A apólice A é melhor neste ponto.")).compare("r", a, b)
    x = field(verdict, "exclusions:poluicao_ambiental")
    assert x.status == ComparisonStatus.REVIEW_REQUIRED and "melhor" not in x.reason
    bogus = ComparisonAgent(Judge("ONLY_A")).compare("r", a, b)
    assert field(bogus, "exclusions:poluicao_ambiental").status == ComparisonStatus.REVIEW_REQUIRED


def test_openai_semantic_comparator_batches_and_falls_back_on_error():
    class Responses:
        def __init__(self): self.calls = 0
        def create(self, **req):
            self.calls += 1
            assert req["text"]["format"]["strict"] is True
            out = {"results": [{"index": 0, "status": "DIFFERENT", "confidence": 0.9, "reason": "Escopos distintos."}]}
            return type("R", (), {"output_text": json.dumps(out)})()
    responses = Responses()
    judge = OpenAISemanticComparator(model="m", client=type("C", (), {"responses": responses})())
    out = judge.compare_many([("exclusions:x", {"name": "a"}, {"name": "b"}), ("exclusions:y", {}, {})])
    assert responses.calls == 1
    assert out[0]["status"] == "DIFFERENT" and out[1]["status"] == "REVIEW_REQUIRED"

    class Broken:
        def create(self, **req): raise RuntimeError("down")
    judge = OpenAISemanticComparator(model="m", client=type("C", (), {"responses": Broken()})())
    assert judge.compare("f", {"a": 1}, {"b": 2})["status"] == "REVIEW_REQUIRED"


def test_strict_schema_exposes_category_enum():
    from llm.schema_contract import strict_policy_json_schema
    schema = strict_policy_json_schema(PolicySchema.model_json_schema())
    assert "poluicao_ambiental" in json.dumps(schema)


def test_combined_dolo_wording_maps_to_dolo():
    x = pol("B", exclusions=[{"name": "Conduta dolosa, fraude, infração dolosa e vantagem indevida"}]).exclusions[0]
    assert categorize(ExclusionCategory, x) == ExclusionCategory.DOLO_FRAUDE


class Matcher(Judge):
    def __init__(self, matches, **kw):
        super().__init__(**kw); self.matches = matches; self.orphans = None
    def match_orphans(self, oa, ob):
        self.orphans = (oa, ob); return self.matches


def orphan_policies():
    a = pol("A", coverages=[{"name": "Advogados internos"}, {"name": "Assessores dos segurados"}],
            exclusions=[{"name": "Direitos autorais"}])
    b = pol("B", clauses=[{"name": "Cobertura para consultores jurídicos internos"}],
            coverages=[{"name": "Extensão para assessores"}], exclusions=[{"name": "Propriedade intelectual"}])
    return a, b


def test_orphans_are_paired_and_judged():
    a, b = orphan_policies()
    oa_expected = ["coverages:advogados internos", "coverages:assessores dos segurados", "exclusions:direitos autorais"]
    # A order: coverages..., exclusions; B order: coverages, exclusions, clauses (see compare()).
    m = Matcher([{"a": 0, "b": 2, "confidence": 0.9}, {"a": 2, "b": 1, "confidence": 0.8}], status="DIFFERENT")
    r = ComparisonAgent(m).compare("r", a, b)
    assert [o["label"] for o in m.orphans[0]][0].startswith("Cobertura: Advogados")
    x = field(r, oa_expected[0])
    assert x.policy_b.value is not None and x.status == ComparisonStatus.DIFFERENT
    assert x.reason.startswith("Pareado por similaridade")
    assert not any(f.field == "clauses:cobertura para consultores juridicos internos" for f in r.fields)
    assert field(r, oa_expected[2]).policy_b.value["name"] == "Propriedade intelectual"


def test_orphan_matching_rejects_cross_family_low_confidence_and_reuse():
    a, b = orphan_policies()
    m = Matcher([{"a": 2, "b": 0, "confidence": 0.99},   # exclusion x coverage: different family
                 {"a": 1, "b": 0, "confidence": 0.5},    # below threshold
                 {"a": 0, "b": 2, "confidence": 0.9}, {"a": 1, "b": 2, "confidence": 0.95},  # b reused
                 {"a": 9, "b": 0, "confidence": 0.99}])  # invalid index
    r = ComparisonAgent(m).compare("r", a, b)
    paired = [x for x in r.fields if x.reason and x.reason.startswith("Pareado")]
    assert len(paired) == 1 and paired[0].field == "coverages:assessores dos segurados"


def test_side_coverage_items_feed_insuring_sides_not_orphans():
    a = pol("A", coverages=[{"name": "Directors and officers liability side A", "category": "cobertura_a", "source_reference": {"page": 34}}])
    b = pol("B", insuring_agreements=[{"side": "A", "present": True}])
    r = ComparisonAgent().compare("r", a, b)
    assert field(r, "insuring_side_A").status == ComparisonStatus.EQUAL
    assert not any(x.field.startswith("coverages:") for x in r.fields)
