from schemas.policy import PolicySchema
from evaluation.golden_resolvers import OUT_OF_SCHEMA, exclusion_concept_keys, resolve
from evaluation.models import GoldenPolicyAnnotation
from evaluation.run_live_golden import eval_02, eval_03


def policy(**kw):
    base = {"document_id": "d", "source_file": "f.pdf"}
    return PolicySchema.model_validate({**base, **kw})


def test_concept_resolvers():
    p = policy(policy_type="Seguro de Responsabilidade Civil de Diretores (D&O)",
               territorial_scope="Qualquer parte do mundo, salvo indicação diversa na Especificação",
               insuring_agreements=[{"side": "A", "present": True, "source_reference": {"page": 34}}],
               exclusions=[{"name": "Riscos cibernéticos", "source_reference": {"page": 17}}])
    assert resolve(p, "policy_type")[0] == "D&O"
    assert resolve(p, "territorial_scope")[0] == "WORLDWIDE_UNLESS_SPECIFIED"
    value, refs = resolve(p, "insuring_agreements.A.present")
    assert value is True and refs[0].page == 34
    value, refs = resolve(p, "exclusion.cyber")
    assert value is True and refs[0].page == 17
    assert resolve(p, "exclusion.pollution")[0] is None
    assert resolve(p, "retention_rule")[0] == OUT_OF_SCHEMA


def test_eval_02_excludes_out_of_schema_and_eval_03_checks_cited_page():
    p = policy(exclusions=[{"name": "Poluição", "source_reference": {"page": 16}}])
    gold = GoldenPolicyAnnotation(document_id="G", source_file="f.pdf", annotations=[
        {"field": "policy_number", "expected": None},
        {"field": "exclusion.pollution", "expected": True, "source_page": 16, "source_excerpt": "x"},
        {"field": "claims_basis", "expected": "CLAIMS_MADE"},
    ])
    r2 = eval_02(p, gold)
    assert (r2.numerator, r2.denominator) == (2, 2)
    assert r2.details["out_of_schema_fields"] == ["claims_basis"]
    r3 = eval_03(p, gold)
    assert (r3.numerator, r3.denominator) == (1, 1)


def test_exclusion_concept_keys_bridges_languages():
    fields = ["exclusions:cyber_risks_and_data_loss", "exclusions:riscos cibernéticos", "exclusions:tributos"]
    assert exclusion_concept_keys(fields, "cyber") == fields[:2]
