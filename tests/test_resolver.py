import pytest

from llm_startup_arena.domain import Client, Company, Employee, EmployeeRole, GameState
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


def build_payroll_state(*, cash: int, morale: int = 70, loyalty: int = 70) -> GameState:
    state = build_state(cash=cash)
    state.companies[0].employees = [
        Employee(
            id="employee-1",
            name="Employee One",
            role=EmployeeRole.ENGINEER,
            skill=60,
            salary=20_000,
            morale=morale,
            loyalty=loyalty,
        ),
        Employee(
            id="employee-2",
            name="Employee Two",
            role=EmployeeRole.SALES,
            skill=60,
            salary=10_000,
            morale=morale,
            loyalty=loyalty,
        ),
    ]
    return state


def test_payroll_deducts_all_employee_salaries() -> None:
    state = build_payroll_state(cash=100_000)

    resolved = RoundResolver().process_payroll(state)

    assert resolved.companies[0].cash == 70_000
    assert resolved.companies[0].reputation == 50
    assert [employee.morale for employee in resolved.companies[0].employees] == [70, 70]
    assert state.companies[0].cash == 100_000


def test_exact_cash_covers_payroll_without_penalties() -> None:
    state = build_payroll_state(cash=30_000)

    resolved = RoundResolver().process_payroll(state)

    assert resolved.companies[0].cash == 0
    assert resolved.companies[0].reputation == 50
    assert [employee.morale for employee in resolved.companies[0].employees] == [70, 70]


def test_unpaid_payroll_applies_company_and_employee_penalties() -> None:
    state = build_payroll_state(cash=20_000, morale=10, loyalty=5)

    resolved = RoundResolver().process_payroll(state)

    company = resolved.companies[0]
    assert company.cash == 0
    assert company.reputation == 45
    assert [employee.morale for employee in company.employees] == [0, 0]
    assert [employee.loyalty for employee in company.employees] == [0, 0]


def test_targeted_client_signs_contract_and_pays_revenue() -> None:
    state = build_state(cash=100_000)
    state.clients = [
        Client(id="client-1", name="Client One", segment="startup", revenue_per_round=12_000)
    ]
    decision = CompanyDecision(
        strategy="acquire client",
        budget=BudgetAllocation(),
        target_client_ids=["client-1"],
    )

    resolved = RoundResolver().resolve_clients(state, {"nova": decision})

    company = resolved.companies[0]
    client = resolved.clients[0]
    assert company.cash == 112_000
    assert company.client_ids == ["client-1"]
    assert client.company_id == "nova"
    assert client.contract_rounds_remaining == 2


def test_client_chooses_company_with_best_product_and_reputation() -> None:
    state = build_state(cash=100_000, product_score=20, reputation=50)
    state.companies.append(
        Company(
            id="orbit",
            name="Orbit",
            model="test-model-2",
            cash=100_000,
            product_score=40,
            reputation=60,
        )
    )
    state.clients = [
        Client(id="client-1", name="Client One", segment="startup", revenue_per_round=8_000)
    ]
    decisions = {
        company_id: CompanyDecision(
            strategy="acquire",
            budget=BudgetAllocation(),
            target_client_ids=["client-1"],
        )
        for company_id in ("nova", "orbit")
    }

    resolved = RoundResolver().resolve_clients(state, decisions)

    assert resolved.clients[0].company_id == "orbit"
    assert resolved.companies[0].client_ids == []
    assert resolved.companies[1].client_ids == ["client-1"]
    assert resolved.companies[1].cash == 108_000


def test_expiring_contract_pays_final_revenue_and_releases_client() -> None:
    state = build_state(cash=100_000)
    state.companies[0].client_ids = ["client-1"]
    state.clients = [
        Client(
            id="client-1",
            name="Client One",
            segment="startup",
            revenue_per_round=10_000,
            company_id="nova",
            contract_rounds_remaining=1,
        )
    ]

    resolved = RoundResolver().resolve_clients(state, {})

    assert resolved.companies[0].cash == 110_000
    assert resolved.companies[0].client_ids == []
    assert resolved.clients[0].company_id is None
    assert resolved.clients[0].contract_rounds_remaining == 0
