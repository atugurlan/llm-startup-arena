from collections.abc import Callable

from llm_startup_arena.domain import GameState

from .provider import CompanyDecision, LLMProvider
from .round_record import RoundDecisionRecord


class DecisionCoordinator:
    """Collect one decision per company from a shared round snapshot."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def collect(
        self,
        state: GameState,
        on_decision: Callable[[str, CompanyDecision], None] | None = None,
    ) -> RoundDecisionRecord:
        snapshot = state.model_copy(deep=True)
        decisions = {}
        for company in snapshot.companies:
            decision = self._provider.generate_decision(
                model=company.model,
                company_id=company.id,
                state=snapshot,
            )
            decisions[company.id] = decision
            if on_decision is not None:
                on_decision(company.id, decision)

        return RoundDecisionRecord(
            round_number=state.round_number + 1,
            decisions=decisions,
        )
