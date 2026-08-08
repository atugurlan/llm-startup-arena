import pytest

from llm_startup_arena.config import DEFAULT_MODELS, GameConfig
from llm_startup_arena.domain import Client, Company, Employee, EmployeeRole, GameState
from llm_startup_arena.engine import GameFactory, RoundResolver
from llm_startup_arena.llm import BudgetAllocation, CompanyDecision, SabotageAction


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
    assert resolved.last_round_events["nova"] == [
        "Total budget spent: $180,000.",
        "Product: +5 investment, +0 role bonus.",
        "Reputation: +3 investment, +0 role bonus.",
    ]


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
    assert resolved.last_round_events["nova"] == ["Clients: won 1; revenue +$12,000."]


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


def test_training_improves_every_employee_and_caps_skill() -> None:
    state = build_payroll_state(cash=100_000)
    state.companies[0].employees[0].skill = 99
    state.companies[0].employees[1].skill = 60
    decision = build_decision(training=50_000)

    resolved = RoundResolver().resolve_training(state, {"nova": decision})

    employees = resolved.companies[0].employees
    assert [employee.skill for employee in employees] == [100, 62]
    assert [employee.experience for employee in employees] == [2, 2]
    assert [employee.skill for employee in state.companies[0].employees] == [99, 60]


def test_training_below_one_level_has_no_employee_effect() -> None:
    state = build_payroll_state(cash=100_000)

    resolved = RoundResolver().resolve_training(
        state,
        {"nova": build_decision(training=24_999)},
    )

    assert resolved.companies[0].employees == state.companies[0].employees


def test_retention_improves_every_employee_and_caps_scores() -> None:
    state = build_payroll_state(cash=100_000, morale=95, loyalty=98)
    decision = build_decision(retention=40_000)

    resolved = RoundResolver().resolve_retention(state, {"nova": decision})

    employees = resolved.companies[0].employees
    assert [employee.morale for employee in employees] == [99, 99]
    assert [employee.loyalty for employee in employees] == [100, 100]
    assert [employee.morale for employee in state.companies[0].employees] == [95, 95]


def test_retention_below_one_level_has_no_employee_effect() -> None:
    state = build_payroll_state(cash=100_000)

    resolved = RoundResolver().resolve_retention(
        state,
        {"nova": build_decision(retention=19_999)},
    )

    assert resolved.companies[0].employees == state.companies[0].employees


def make_employee(
    employee_id: str,
    role: EmployeeRole,
    *,
    skill: int,
    salary: int = 0,
) -> Employee:
    return Employee(
        id=employee_id,
        name=employee_id,
        role=role,
        skill=skill,
        salary=salary,
    )


def test_product_and_marketing_roles_amplify_relevant_investments() -> None:
    state = build_state(cash=200_000)
    state.companies[0].employees = [
        make_employee("engineer-1", EmployeeRole.ENGINEER, skill=60),
        make_employee("engineer-2", EmployeeRole.ENGINEER, skill=40),
        make_employee("product-1", EmployeeRole.PRODUCT, skill=50),
        make_employee("marketing-1", EmployeeRole.MARKETING, skill=50),
    ]

    resolved = RoundResolver().resolve_investments(
        state,
        {"nova": build_decision(product=20_000, marketing=20_000)},
    )

    assert resolved.companies[0].product_score == 23
    assert resolved.companies[0].reputation == 52


def test_role_bonus_requires_relevant_investment() -> None:
    state = build_state(cash=100_000)
    state.companies[0].employees = [
        make_employee("engineer-1", EmployeeRole.ENGINEER, skill=100),
        make_employee("marketing-1", EmployeeRole.MARKETING, skill=100),
    ]

    resolved = RoundResolver().resolve_investments(
        state,
        {"nova": build_decision(training=25_000)},
    )

    assert resolved.companies[0].product_score == 20
    assert resolved.companies[0].reputation == 50


def test_sales_role_can_win_client_competition() -> None:
    state = build_state(cash=100_000, product_score=20, reputation=50)
    state.companies[0].employees = [make_employee("sales-1", EmployeeRole.SALES, skill=50)]
    state.companies.append(
        Company(
            id="orbit",
            name="Orbit",
            model="test-model-2",
            cash=100_000,
            product_score=21,
            reputation=50,
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

    assert resolved.clients[0].company_id == "nova"


def test_operations_role_reduces_payroll_up_to_twenty_percent() -> None:
    state = build_state(cash=100_000)
    state.companies[0].employees = [
        make_employee(
            "operations-1",
            EmployeeRole.OPERATIONS,
            skill=100,
            salary=10_000,
        )
    ]

    resolved = RoundResolver().process_payroll(state)

    assert resolved.companies[0].cash == 92_000


def test_low_morale_halves_employee_role_power() -> None:
    state = build_state(cash=100_000)
    employee = make_employee("marketing-1", EmployeeRole.MARKETING, skill=100)
    employee.morale = 39
    state.companies[0].employees = [employee]

    resolved = RoundResolver().resolve_investments(
        state,
        {"nova": build_decision(marketing=20_000)},
    )

    assert resolved.companies[0].reputation == 52


def test_employee_below_loyalty_threshold_leaves_and_creates_event() -> None:
    state = build_payroll_state(cash=100_000, loyalty=39)

    resolved = RoundResolver().resolve_departures(state)

    assert resolved.companies[0].employees == []
    assert resolved.last_round_events == {
        "nova": [
            "Employee One left the company (loyalty: 39).",
            "Employee Two left the company (loyalty: 39).",
        ]
    }
    assert len(state.companies[0].employees) == 2


def test_retention_can_prevent_departure_in_same_round() -> None:
    state = build_payroll_state(cash=100_000, loyalty=39)

    resolved = RoundResolver().resolve_round(
        state,
        {"nova": build_decision(retention=20_000)},
    )

    assert len(resolved.companies[0].employees) == 2
    assert [employee.loyalty for employee in resolved.companies[0].employees] == [41, 41]
    assert resolved.last_round_events["nova"] == [
        "Total budget spent: $20,000.",
        "Retention: 2 employees gained +2 morale and loyalty.",
        "Payroll paid: -$30,000.",
        "Round-end cash: $50,000.",
    ]


def test_unpaid_payroll_can_trigger_departures_in_same_round() -> None:
    state = build_payroll_state(cash=20_000, loyalty=50)

    resolved = RoundResolver().resolve_round(state, {})

    assert resolved.companies[0].employees == []
    assert resolved.last_round_events["nova"] == [
        "Payroll missed: needed $30,000; morale -20, loyalty -15, reputation -5.",
        "Employee One left the company (loyalty: 35).",
        "Employee Two left the company (loyalty: 35).",
        "Round-end cash: $0.",
    ]


def test_employees_start_leaving_after_two_unpaid_rounds() -> None:
    state = build_payroll_state(cash=20_000, loyalty=65)

    first_round = RoundResolver().resolve_round(state, {})
    second_round = RoundResolver().resolve_round(first_round, {})

    assert len(first_round.companies[0].employees) == 2
    assert [employee.loyalty for employee in first_round.companies[0].employees] == [50, 50]
    assert second_round.companies[0].employees == []


def test_external_candidate_joins_winning_company() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    state.companies[0].product_score = 80
    state.companies[1].product_score = 20
    decisions = {
        company_id: CompanyDecision(
            strategy="hire ambitious engineer",
            budget=BudgetAllocation(recruitment=20_000),
            target_candidate_ids=["candidate-alex-chen"],
        )
        for company_id in ("nova", "orbit")
    }

    resolved = RoundResolver().resolve_recruitment(state, decisions)

    assert any(employee.id == "candidate-alex-chen" for employee in resolved.companies[0].employees)
    assert all(employee.id != "candidate-alex-chen" for employee in resolved.companies[1].employees)
    assert all(candidate.id != "candidate-alex-chen" for candidate in resolved.available_candidates)
    assert resolved.last_round_events["nova"] == ["Hired Alex Chen (engineer, ambitious)."]
    assert resolved.last_round_events["orbit"] == ["Hiring: no external offer was accepted."]
    assert len(state.available_candidates) == 5


def test_external_offer_below_minimum_is_not_accepted() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    decision = CompanyDecision(
        strategy="underfunded hiring",
        budget=BudgetAllocation(recruitment=19_999),
        target_candidate_ids=["candidate-elena-ionescu"],
    )

    resolved = RoundResolver().resolve_recruitment(state, {"nova": decision})

    assert len(resolved.companies[0].employees) == 5
    assert len(resolved.available_candidates) == 5
    assert resolved.last_round_events["nova"] == ["Hiring: no external offer was accepted."]


def test_company_can_recruit_competitor_employee() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    state.companies[0].product_score = 80
    state.companies[0].reputation = 100
    employee_id = "orbit-employee-1"
    decision = CompanyDecision(
        strategy="recruit competitor engineer",
        budget=BudgetAllocation(recruitment=100_000),
        target_employee_ids=[employee_id],
    )

    resolved = RoundResolver().resolve_recruitment(state, {"nova": decision})

    assert any(employee.id == employee_id for employee in resolved.companies[0].employees)
    assert all(employee.id != employee_id for employee in resolved.companies[1].employees)
    assert resolved.last_round_events["nova"] == ["Recruited Orbit Employee 1 from Orbit AI."]
    assert resolved.last_round_events["orbit"] == ["Lost Orbit Employee 1 to Nova Labs."]
    assert len(state.companies[0].employees) == 5
    assert len(state.companies[1].employees) == 5


def test_retention_can_defend_employee_from_poaching() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    decisions = {
        "nova": CompanyDecision(
            strategy="recruit competitor engineer",
            budget=BudgetAllocation(recruitment=40_000),
            target_employee_ids=["orbit-employee-1"],
        ),
        "orbit": CompanyDecision(
            strategy="retain team",
            budget=BudgetAllocation(retention=40_000),
        ),
    }

    resolved = RoundResolver().resolve_recruitment(state, decisions)

    assert len(resolved.companies[0].employees) == 5
    assert len(resolved.companies[1].employees) == 5
    assert resolved.last_round_events["nova"] == ["Poaching: no employee offer was accepted."]


@pytest.mark.parametrize(
    ("action", "attribute", "starting_value", "expected_value", "effect"),
    [
        (
            SabotageAction.PRODUCT_DISRUPTION,
            "product_score",
            20,
            16,
            "product score -4.",
        ),
        (
            SabotageAction.REPUTATION_ATTACK,
            "reputation",
            50,
            46,
            "reputation -4.",
        ),
    ],
)
def test_sabotage_reduces_target_company_score(
    action: SabotageAction,
    attribute: str,
    starting_value: int,
    expected_value: int,
    effect: str,
) -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    target = state.companies[1]
    setattr(target, attribute, starting_value)
    decision = CompanyDecision(
        strategy="attack competitor",
        budget=BudgetAllocation(sabotage=40_000),
        sabotage_action=action,
        target_company_id=target.id,
    )

    resolved = RoundResolver().resolve_sabotage(state, {"nova": decision})

    assert getattr(resolved.companies[1], attribute) == expected_value
    assert getattr(state.companies[1], attribute) == starting_value
    assert resolved.last_round_events["nova"] == [f"Sabotage against Orbit AI: {effect}"]
    assert resolved.last_round_events["orbit"] == [f"Sabotaged by Nova Labs: {effect}"]


def test_client_interference_shortens_contracts_and_releases_expiring_client() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    target = state.companies[1]
    for client, remaining in zip(state.clients[:2], (1, 3), strict=True):
        client.company_id = target.id
        client.contract_rounds_remaining = remaining
        target.client_ids.append(client.id)
    decision = CompanyDecision(
        strategy="disrupt contracts",
        budget=BudgetAllocation(sabotage=40_000),
        sabotage_action=SabotageAction.CLIENT_INTERFERENCE,
        target_company_id=target.id,
    )

    resolved = RoundResolver().resolve_sabotage(state, {"nova": decision})

    assert resolved.clients[0].company_id is None
    assert resolved.clients[0].contract_rounds_remaining == 0
    assert resolved.clients[1].company_id == "orbit"
    assert resolved.clients[1].contract_rounds_remaining == 2
    assert resolved.companies[1].client_ids == [resolved.clients[1].id]
    assert resolved.last_round_events["nova"] == [
        "Sabotage against Orbit AI: 2 client contract(s) shortened; 1 client(s) released."
    ]


def test_talent_disruption_reduces_target_employee_morale_and_loyalty() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    target = state.companies[1]
    initial_morale = [employee.morale for employee in target.employees]
    initial_loyalty = [employee.loyalty for employee in target.employees]
    decision = CompanyDecision(
        strategy="disrupt team",
        budget=BudgetAllocation(sabotage=40_000),
        sabotage_action=SabotageAction.TALENT_DISRUPTION,
        target_company_id=target.id,
    )

    resolved = RoundResolver().resolve_sabotage(state, {"nova": decision})
    employees = resolved.companies[1].employees

    assert [employee.morale for employee in employees] == [
        max(0, morale - 8) for morale in initial_morale
    ]
    assert [employee.loyalty for employee in employees] == [
        max(0, loyalty - 4) for loyalty in initial_loyalty
    ]
    assert resolved.last_round_events["orbit"] == [
        "Sabotaged by Nova Labs: 5 employees lost up to 8 morale and 4 loyalty."
    ]
