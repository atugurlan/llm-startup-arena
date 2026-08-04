from llm_startup_arena.domain import GameState

from .provider import LLMProvider
from .round_record import RoundDecisionRecord


class DecisionCoordinator:
    """Collect one decision per company from a shared round snapshot."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def collect(self, state: GameState) -> RoundDecisionRecord:
        snapshot = state.model_copy(deep=True)
        decisions = {
            company.id: self._provider.generate_decision(
                model=company.model,
                company_id=company.id,
                state=snapshot,
            )
            for company in snapshot.companies
        }
        return RoundDecisionRecord(
            round_number=state.round_number + 1,
            decisions=decisions,
        )
