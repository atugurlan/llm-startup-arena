import pytest

from llm_startup_arena.domain import Client, Company, Employee, EmployeeRole, GameState
from llm_startup_arena.engine import CompanyRanker, GameResult


def test_ranker_calculates_every_valuation_component() -> None:
    company = Company(
        id="nova",
        name="Nova Labs",
        model="test-model",
        cash=100_000,
        product_score=10,
        reputation=20,
        client_ids=["client-1"],
        employees=[
            Employee(
                id="employee-1",
                name="Employee One",
                role=EmployeeRole.ENGINEER,
                skill=50,
                salary=5_000,
                experience=4,
                morale=80,
                loyalty=60,
            )
        ],
    )
    client = Client(
        id="client-1",
        name="Client One",
        segment="startup",
        revenue_per_round=10_000,
        contract_rounds_remaining=2,
        company_id="nova",
    )

    score = CompanyRanker().rank(GameState(companies=[company], clients=[client])).winner

    assert score.cash_value == 100_000
    assert score.product_value == 50_000
    assert score.reputation_value == 100_000
    assert score.client_value == 20_000
    assert score.employee_value == 87_000
    assert score.total_value == 357_000


def test_ranker_orders_companies_and_assigns_positions() -> None:
    state = GameState(
        companies=[
            Company(id="product", name="Product", model="model-a", cash=0, product_score=20),
            Company(id="cash", name="Cash", model="model-b", cash=100_000),
            Company(id="leader", name="Leader", model="model-c", cash=200_000),
        ],
        clients=[],
    )

    result = CompanyRanker().rank(state)

    assert [score.company_id for score in result.rankings] == ["leader", "cash", "product"]
    assert [score.position for score in result.rankings] == [1, 2, 3]
    assert result.winner.company_id == "leader"


def test_ranker_uses_company_id_as_final_deterministic_tiebreaker() -> None:
    state = GameState(
        companies=[
            Company(id="zeta", name="Zeta", model="model-z", cash=100_000),
            Company(id="alpha", name="Alpha", model="model-a", cash=100_000),
        ],
        clients=[],
    )

    result = CompanyRanker().rank(state)

    assert [score.company_id for score in result.rankings] == ["alpha", "zeta"]


def test_empty_result_has_no_winner() -> None:
    with pytest.raises(ValueError, match="without ranked companies"):
        _ = GameResult(rankings=[]).winner
