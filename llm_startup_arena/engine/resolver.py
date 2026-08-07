from collections.abc import Mapping

from llm_startup_arena.domain import GameState
from llm_startup_arena.llm.provider import BudgetAllocation, CompanyDecision

INVESTMENT_PER_SCORE_POINT = 20_000
UNPAID_PAYROLL_MORALE_PENALTY = 20
UNPAID_PAYROLL_LOYALTY_PENALTY = 10
UNPAID_PAYROLL_REPUTATION_PENALTY = 5
CLIENT_CONTRACT_ROUNDS = 3
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
                company.product_score + decision.budget.product // INVESTMENT_PER_SCORE_POINT,
            )
            company.reputation = min(
                100,
                company.reputation + decision.budget.marketing // INVESTMENT_PER_SCORE_POINT,
            )
        return resolved

    def resolve_recruitment(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        return state

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
                key=lambda company: company.product_score + company.reputation,
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
            payroll = sum(employee.salary for employee in company.employees)
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
