import pytest
from pydantic import ValidationError
from schemas.policy import PolicySchema, Money, Coverage
from schemas.comparison import ComparisonStatus, ComparedValue, FieldComparison, ComparisonResult
from orchestration.state import RunStatus
from orchestration.orchestrator import Orchestrator, InvalidTransitionError


def test_policy_schema_valid():
    policy = PolicySchema(
        document_id="doc-a",
        source_file="a.pdf",
        insurer="Seguradora X",
        currency="brl",
        limit_of_liability=Money(amount=10_000_000, currency="brl"),
        coverages=[Coverage(name="Side A")],
    )
    assert policy.currency == "BRL"
    assert policy.limit_of_liability.currency == "BRL"


def test_policy_schema_rejects_extra_field():
    with pytest.raises(ValidationError):
        PolicySchema(document_id="doc-a", source_file="a.pdf", invented_field="x")


def test_comparison_schema_valid():
    field = FieldComparison(
        field="limit_of_liability",
        policy_a=ComparedValue(value=10_000_000),
        policy_b=ComparedValue(value=5_000_000),
        status=ComparisonStatus.DIFFERENT,
        confidence=1.0,
    )
    result = ComparisonResult(
        run_id="run-1",
        policy_a_document_id="a",
        policy_b_document_id="b",
        fields=[field],
    )
    assert result.fields[0].status == ComparisonStatus.DIFFERENT


def test_orchestrator_happy_path_to_extracting():
    orch = Orchestrator()
    state = orch.start_run()
    assert state.status == RunStatus.CREATED
    orch.update_state(state, RunStatus.INGESTING, "A1")
    orch.update_state(state, RunStatus.EXTRACTING, "A2")
    assert state.status == RunStatus.EXTRACTING
    assert len(state.trace) == 3


def test_orchestrator_blocks_invalid_transition():
    orch = Orchestrator()
    state = orch.start_run()
    with pytest.raises(InvalidTransitionError):
        orch.update_state(state, RunStatus.COMPARING, "A5")
