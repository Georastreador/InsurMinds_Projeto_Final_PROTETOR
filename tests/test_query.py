from agents.query_agent import QueryAgent, StoredDocument, catalog, retrieve_pages, search
from schemas.policy import PolicySchema
from storage.database import Database
from tools.text_budget import join_pages


def policy(doc, insurer, **kw):
    return PolicySchema.model_validate({"document_id": doc, "source_file": f"{doc}.pdf", "insurer": insurer, **kw})


def stored(p):
    return StoredDocument(p.document_id, "run", "2026-09-30T12:00", p)


def test_catalog_keeps_latest_version_per_file(tmp_path):
    db = Database(tmp_path / "q.db")
    db.save_policy("r1", policy("chubb", "Chubb antiga"))
    db.save_policy("r2", policy("chubb", "Chubb nova"))
    db.save_policy("r2", policy("sompo", "Sompo"))
    docs = catalog(db)
    assert [d.policy.insurer for d in docs] == ["Sompo", "Chubb nova"]


def test_search_is_accent_insensitive_and_filters_groups():
    docs = [stored(policy("a", "Chubb", exclusions=[{"name": "Riscos cibernéticos", "category": "cibernetico", "source_reference": {"page": 65}}],
                          coverages=[{"name": "Custos de defesa"}])),
            stored(policy("b", "Sompo", exclusions=[{"name": "Responsabilidade cibernética"}]))]
    rows = search(docs, "cibernetico")
    assert {r["Seguradora"] for r in rows} == {"Chubb", "Sompo"} and rows[0]["Página"] == 65
    assert search(docs, "cibernetico", {"coverages"}) == []
    assert len(search(docs, "custos defesa")) == 1


def test_retrieve_pages_ranks_by_question_terms():
    text = join_pages([{"page": 1, "text": "capa"}, {"page": 2, "text": "franquia franquia cobertura A"},
                       {"page": 3, "text": "foro e arbitragem"}])
    assert [p["page"] for p in retrieve_pages(text, "Qual a franquia da cobertura A?")] == [2]


class Responder:
    model = "fake"
    def __init__(self, out): self.out, self.context = out, None
    def respond(self, question, context):
        self.context = context; return self.out


def docs_for_answer():
    a = stored(policy("a", "Chubb")); b = stored(policy("b", "Sompo"))
    ta = join_pages([{"page": 8, "text": "Franquia conforme Especificação"}, {"page": 9, "text": "outro"}])
    tb = join_pages([{"page": 39, "text": "Não se aplica franquia na Cobertura A"}])
    return [("A", a, ta), ("B", b, tb)]


def test_answer_keeps_only_citations_of_pages_sent():
    r = Responder({"answer": "A remete à Especificação [A p.8]; B dispensa [B p.39].", "found": True,
                   "citations": [{"doc": "A", "page": 8}, {"doc": "B", "page": 39}, {"doc": "B", "page": 99}]})
    out = QueryAgent(r).answer("Como é a franquia?", docs_for_answer())
    assert out["citations"] == [{"doc": "A", "page": 8}, {"doc": "B", "page": 39}]
    assert "1 citação" in out["note"] and "[A p.8]" in r.context


def test_answer_refuses_verdicts_and_works_offline():
    verdict = QueryAgent(Responder({"answer": "A Chubb é melhor.", "found": True, "citations": []})).answer("franquia?", docs_for_answer())
    assert verdict["answer"] is None and "veredito" in verdict["note"]
    offline = QueryAgent(None).answer("franquia?", docs_for_answer())
    assert offline["answer"] is None and offline["excerpts"]["B"][0]["page"] == 39
