import pytest
from guardrails.verdict import VerdictGuard, has_verdict, verdict_matches

# Phrases that passed the v1.2 word list and must now be blocked.
ADVERSARIAL = [
    "Recomenda-se contratar a apólice A.",
    "A apólice A é mais vantajosa e superior à B.",
    "B oferece proteção mais ampla e preferível.",
    "Sugere-se optar pela Sompo.",
    "O analista deveria escolher a Chubb.",
    "Deve-se contratar o documento B.",
    "A Chubb é claramente superior.",
    "A Sompo é inferior à Chubb.",
    "Para o segurado, B é a opção ideal.",
    "A é menos favorável ao segurado.",
    "Vale a pena ficar com a apólice B.",
    "Aconselhamos a contratação de A.",
    "Opte pela apólice A.",
    "Policy A is more advantageous than B.",
    "We recommend policy B.",
    "Policy A is superior to policy B.",
    "A Chubb leva vantagem em custos de defesa.",
    "A é a escolha certa para administradores.",
    "A é a melhor.",
    "B é mais protetiva para os diretores.",
]

# Factual descriptions that must keep passing (false positives would discard valid syntheses).
FACTUAL = [
    "O limite de B é superior a R$ 10 milhões.",
    "A franquia de A é inferior à de B em R$ 50 mil.",
    "A seguradora empregará seus melhores esforços na regulação.",
    "A escolha do advogado cabe ao Segurado, com anuência da Seguradora.",
    "B prevê cobertura mais ampla para custos de defesa.",
    "A Chubb exclui perda de dados; a Sompo exclui ataques cibernéticos e malware.",
    "O prazo complementar da Chubb é de até 36 meses; na Sompo não foi identificado.",
    "Limite máximo de garantia superior a 1 milhão de reais.",
    "Valor inferior a R$ 5.000,00 não é indenizado.",
    "As coberturas A e B devem ser contratadas simultaneamente.",
    "Pelo menos uma cobertura básica deve ser contratada.",
    "A cobertura de B abrange multas e penalidades; em A depende de cobertura adicional.",
]


@pytest.mark.parametrize("text", ADVERSARIAL)
def test_adversarial_verdicts_are_blocked(text):
    assert has_verdict(text), text


@pytest.mark.parametrize("text", FACTUAL)
def test_factual_differences_are_not_blocked(text):
    assert not has_verdict(text), (text, verdict_matches(text))


class FakeClassifier:
    def __init__(self, verdict=False, error=None):
        self.verdict, self.error, self.calls = verdict, error, 0

    def classify(self, text):
        self.calls += 1
        if self.error:
            raise self.error
        return {"verdict": self.verdict, "reason": "preferência implícita"}


def test_guard_uses_classifier_only_after_patterns_pass():
    clf = FakeClassifier(verdict=True)
    guard = VerdictGuard(clf)
    assert guard.check("A é melhor.").layer == "patterns" and clf.calls == 0
    result = guard.check("No conjunto, a Sompo atende de modo mais satisfatório ao perfil do segurado.")
    assert result.blocked and clf.calls == 1


def test_classifier_catches_paraphrase_and_failure_degrades_to_patterns():
    paraphrase = "Considerando tudo, a Sompo atende de modo mais satisfatório ao perfil do segurado."
    assert not has_verdict(paraphrase)
    assert VerdictGuard(FakeClassifier(verdict=True)).check(paraphrase).layer == "classifier"
    failed = VerdictGuard(FakeClassifier(error=RuntimeError("down"))).check(paraphrase)
    assert not failed.blocked and failed.classifier_error == "RuntimeError"
