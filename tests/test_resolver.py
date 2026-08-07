import pytest

from llm_startup_arena.domain import Company, GameState
from llm_startup_arena.engine import RoundResolver
from llm_startup_arena.llm import BudgetAllocation, CompanyDecision


def build_state(*, cash: int = 500_000, product_score: int = 20, reputation: int = 50):
    company = Company(
        id="nova",
        name="Nova",
        model="test-model",
        cash=cash,
        product_score=product_score,
        reputation=reputation,
    )
    return GameState(companies=[company], clients=[])


def build_decision(**budget: int) -> CompanyDecision:
    return CompanyDecision(
        strategy="invest",
        budget=BudgetAllocation(**budget),
    )


def test_investments_deduct_total_budget_and_improve_scores() -> None:
    state = build_state()
    decision = build_decision(
        product=100_000,
        marketing=60_000,
        training=20_000,
    )

    resolved = RoundResolver().resolve_investments(state, {"nova": decision})

    company = resolved.companies[0]
    assert company.cash == 320_000
    assert company.product_score == 25
    assert company.reputation == 53


def test_investments_do_not_mutate_input_state() -> None:
    state = build_state()

    RoundResolver().resolve_investments(
        state,
        {"nova": build_decision(product=100_000)},
    )

    assert state.companies[0].cash == 500_000
    assert state.companies[0].product_score == 20


def test_investment_scores_are_capped_at_one_hundred() -> None:
    state = build_state(product_score=98, reputation=99)

    resolved = RoundResolver().resolve_investments(
        state,
        {"nova": build_decision(product=100_000, marketing=100_000)},
    )

    assert resolved.companies[0].product_score == 100
    assert resolved.companies[0].reputation == 100


def test_company_without_decision_holds_its_position() -> None:
    state = build_state()

    resolved = RoundResolver().resolve_investments(state, {})

    assert resolved == state
    assert resolved is not state


def test_resolver_rejects_overspending_without_mutating_input() -> None:
    state = build_state(cash=50_000)

    with pytest.raises(ValueError, match="only 50000 is available"):
        RoundResolver().resolve_investments(
            state,
            {"nova": build_decision(product=60_000)},
        )

    assert state.companies[0].cash == 50_000
