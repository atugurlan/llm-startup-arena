import pytest

from llm_startup_arena.config import DEFAULT_MODELS, GameConfig
from llm_startup_arena.engine import GameFactory
from llm_startup_arena.llm import (
    BudgetAllocation,
    CompanyDecision,
    DecisionNormalizer,
    DecisionValidationError,
    DecisionValidator,
)


@pytest.fixture
def game_state():
    return GameFactory(GameConfig(), DEFAULT_MODELS).create()


def test_validator_accepts_valid_decision(game_state) -> None:
    decision = CompanyDecision(
        strategy="Acquire a client and recruit from a competitor",
        budget=BudgetAllocation(product=100_000, recruitment=50_000),
        target_client_ids=["client-1"],
        target_employee_ids=["orbit-employee-1"],
    )

    result = DecisionValidator().validate(
        company_id="nova",
        decision=decision,
        state=game_state,
    )

    assert result is decision


def test_normalizer_repairs_recoverable_model_mistakes(game_state) -> None:
    game_state.clients[1].company_id = "orbit"
    game_state.clients[1].contract_rounds_remaining = 2
    decision = CompanyDecision(
        strategy="mixed invalid targets",
        budget=BudgetAllocation(recruitment=10_000, sabotage=20_000),
        target_client_ids=["client-1", "client-2"],
        target_employee_ids=["nova-employee-1", "orbit-employee-1"],
        sabotage_action=None,
    )

    normalized = DecisionNormalizer().normalize(
        company_id="nova",
        decision=decision,
        state=game_state,
    )

    assert normalized.target_client_ids == ["client-1"]
    assert normalized.target_employee_ids == ["orbit-employee-1"]
    assert normalized.budget.sabotage == 0
    assert normalized.sabotage_action is None
    assert decision.target_client_ids == ["client-1", "client-2"]
    assert decision.budget.sabotage == 20_000
    assert (
        DecisionValidator().validate(
            company_id="nova",
            decision=normalized,
            state=game_state,
        )
        is normalized
    )


def test_validator_rejects_unknown_company(game_state) -> None:
    decision = CompanyDecision(strategy="wait", budget=BudgetAllocation())

    with pytest.raises(DecisionValidationError, match="Unknown company"):
        DecisionValidator().validate(
            company_id="missing",
            decision=decision,
            state=game_state,
        )


def test_validator_reports_all_invalid_targets_and_budget(game_state) -> None:
    decision = CompanyDecision(
        strategy="invalid",
        budget=BudgetAllocation(product=600_000),
        target_client_ids=["missing-client", "missing-client"],
        target_employee_ids=["missing-employee", "missing-employee"],
    )

    with pytest.raises(DecisionValidationError) as error:
        DecisionValidator().validate(
            company_id="nova",
            decision=decision,
            state=game_state,
        )

    assert len(error.value.errors) == 5
    assert "exceeds available cash" in str(error.value)
    assert "Duplicate client targets" in str(error.value)
    assert "Unknown or unavailable clients" in str(error.value)
    assert "Duplicate employee targets" in str(error.value)
    assert "Unknown employees" in str(error.value)


def test_validator_rejects_recruiting_own_employee(game_state) -> None:
    decision = CompanyDecision(
        strategy="retain",
        budget=BudgetAllocation(recruitment=10_000),
        target_employee_ids=["nova-employee-1"],
    )

    with pytest.raises(DecisionValidationError, match="Cannot recruit own employees"):
        DecisionValidator().validate(
            company_id="nova",
            decision=decision,
            state=game_state,
        )


def test_validator_rejects_client_already_under_contract(game_state) -> None:
    game_state.clients[0].company_id = "orbit"
    game_state.clients[0].contract_rounds_remaining = 2
    decision = CompanyDecision(
        strategy="target unavailable client",
        budget=BudgetAllocation(marketing=10_000),
        target_client_ids=[game_state.clients[0].id],
    )

    with pytest.raises(DecisionValidationError, match="unavailable clients"):
        DecisionValidator().validate(
            company_id="nova",
            decision=decision,
            state=game_state,
        )


@pytest.mark.parametrize(
    ("budget", "action", "message"),
    [
        (10_000, None, "budget requires a sabotage action"),
        (0, "spread rumors", "action requires a sabotage budget"),
    ],
)
def test_validator_requires_consistent_sabotage(
    game_state,
    budget: int,
    action: str | None,
    message: str,
) -> None:
    decision = CompanyDecision(
        strategy="sabotage",
        budget=BudgetAllocation(sabotage=budget),
        sabotage_action=action,
    )

    with pytest.raises(DecisionValidationError, match=message):
        DecisionValidator().validate(
            company_id="nova",
            decision=decision,
            state=game_state,
        )
