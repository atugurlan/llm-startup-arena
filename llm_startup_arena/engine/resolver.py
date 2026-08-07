from collections.abc import Mapping

from llm_startup_arena.domain import GameState
from llm_startup_arena.llm.provider import CompanyDecision

INVESTMENT_PER_SCORE_POINT = 20_000


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
        return state

    def resolve_sabotage(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        return state

    def process_payroll(self, state: GameState) -> GameState:
        return state
