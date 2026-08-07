from collections.abc import Mapping

from llm_startup_arena.domain import Company, EmployeeRole, GameState
from llm_startup_arena.llm.provider import BudgetAllocation, CompanyDecision

INVESTMENT_PER_SCORE_POINT = 20_000
UNPAID_PAYROLL_MORALE_PENALTY = 20
UNPAID_PAYROLL_LOYALTY_PENALTY = 10
UNPAID_PAYROLL_REPUTATION_PENALTY = 5
CLIENT_CONTRACT_ROUNDS = 3
TRAINING_COST_PER_LEVEL = 25_000
RETENTION_COST_PER_LEVEL = 20_000
RETENTION_POINTS_PER_LEVEL = 2
ENGINEERING_POWER_PER_PRODUCT_POINT = 100
PRODUCT_POWER_PER_PRODUCT_POINT = 50
MARKETING_POWER_PER_REPUTATION_POINT = 50
SALES_POWER_PER_ACQUISITION_POINT = 50
OPERATIONS_POWER_PER_PAYROLL_PERCENT = 5
MAX_PAYROLL_DISCOUNT_PERCENT = 20
_HOLD_DECISION = CompanyDecision(strategy="hold", budget=BudgetAllocation())


class RoundResolver:
    """Apply decisions to a frozen snapshot through deterministic rule stages."""

    def resolve_round(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        resolved = state.model_copy(deep=True)
        resolved = self.resolve_investments(resolved, decisions)
        resolved = self.resolve_training(resolved, decisions)
        resolved = self.resolve_retention(resolved, decisions)
        resolved = self.resolve_recruitment(resolved, decisions)
        resolved = self.resolve_clients(resolved, decisions)
        resolved = self.resolve_sabotage(resolved, decisions)
        resolved = self.process_payroll(resolved)
        resolved.round_number += 1
        return resolved

    def resolve_investments(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        resolved = state.model_copy(deep=True)
        for company in resolved.companies:
            decision = decisions.get(company.id)
            if decision is None:
                continue

            total_budget = decision.budget.total
            if total_budget > company.cash:
                raise ValueError(
                    f"Company {company.id!r} cannot spend {total_budget}; "
                    f"only {company.cash} is available"
                )

            company.cash -= total_budget
            company.product_score = min(
                100,
                company.product_score
                + decision.budget.product // INVESTMENT_PER_SCORE_POINT
                + _product_role_bonus(company, decision),
            )
            company.reputation = min(
                100,
                company.reputation
                + decision.budget.marketing // INVESTMENT_PER_SCORE_POINT
                + _marketing_role_bonus(company, decision),
            )
        return resolved

    def resolve_training(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        resolved = state.model_copy(deep=True)
        for company in resolved.companies:
            decision = decisions.get(company.id)
            if decision is None:
                continue
            training_levels = decision.budget.training // TRAINING_COST_PER_LEVEL
            for employee in company.employees:
                employee.skill = min(100, employee.skill + training_levels)
                employee.experience += training_levels
        return resolved

    def resolve_recruitment(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        return state

    def resolve_retention(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        resolved = state.model_copy(deep=True)
        for company in resolved.companies:
            decision = decisions.get(company.id)
            if decision is None:
                continue
            retention_levels = decision.budget.retention // RETENTION_COST_PER_LEVEL
            retention_points = retention_levels * RETENTION_POINTS_PER_LEVEL
            for employee in company.employees:
                employee.morale = min(100, employee.morale + retention_points)
                employee.loyalty = min(100, employee.loyalty + retention_points)
        return resolved

    def resolve_clients(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        resolved = state.model_copy(deep=True)
        companies = {company.id: company for company in resolved.companies}

        for client in resolved.clients:
            if client.company_id is not None:
                continue
            contenders = [
                company
                for company in resolved.companies
                if client.id in decisions.get(company.id, _HOLD_DECISION).target_client_ids
            ]
            if not contenders:
                continue

            winner = max(
                contenders,
                key=lambda company: (
                    company.product_score + company.reputation + _sales_role_bonus(company)
                ),
            )
            client.company_id = winner.id
            client.contract_rounds_remaining = CLIENT_CONTRACT_ROUNDS
            if client.id not in winner.client_ids:
                winner.client_ids.append(client.id)

        for client in resolved.clients:
            if client.company_id is None:
                continue
            company = companies[client.company_id]
            company.cash += client.revenue_per_round
            client.contract_rounds_remaining -= 1
            if client.contract_rounds_remaining == 0:
                company.client_ids.remove(client.id)
                client.company_id = None

        return resolved

    def resolve_sabotage(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        return state

    def process_payroll(self, state: GameState) -> GameState:
        resolved = state.model_copy(deep=True)
        for company in resolved.companies:
            gross_payroll = sum(employee.salary for employee in company.employees)
            discount_percent = min(
                MAX_PAYROLL_DISCOUNT_PERCENT,
                _role_power(company, EmployeeRole.OPERATIONS)
                // OPERATIONS_POWER_PER_PAYROLL_PERCENT,
            )
            payroll = gross_payroll * (100 - discount_percent) // 100
            if company.cash >= payroll:
                company.cash -= payroll
                continue

            company.cash = 0
            company.reputation = max(
                0,
                company.reputation - UNPAID_PAYROLL_REPUTATION_PENALTY,
            )
            for employee in company.employees:
                employee.morale = max(
                    0,
                    employee.morale - UNPAID_PAYROLL_MORALE_PENALTY,
                )
                employee.loyalty = max(
                    0,
                    employee.loyalty - UNPAID_PAYROLL_LOYALTY_PENALTY,
                )
        return resolved


def _role_power(company: Company, role: EmployeeRole) -> int:
    return sum(employee.skill for employee in company.employees if employee.role == role)


def _product_role_bonus(company: Company, decision: CompanyDecision) -> int:
    if decision.budget.product == 0:
        return 0
    return (
        _role_power(company, EmployeeRole.ENGINEER) // ENGINEERING_POWER_PER_PRODUCT_POINT
        + _role_power(company, EmployeeRole.PRODUCT) // PRODUCT_POWER_PER_PRODUCT_POINT
    )


def _marketing_role_bonus(company: Company, decision: CompanyDecision) -> int:
    if decision.budget.marketing == 0:
        return 0
    return _role_power(company, EmployeeRole.MARKETING) // MARKETING_POWER_PER_REPUTATION_POINT


def _sales_role_bonus(company: Company) -> int:
    return _role_power(company, EmployeeRole.SALES) // SALES_POWER_PER_ACQUISITION_POINT
