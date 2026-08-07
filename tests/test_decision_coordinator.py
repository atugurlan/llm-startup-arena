from llm_startup_arena.config import DEFAULT_MODELS, GameConfig
from llm_startup_arena.domain import GameState
from llm_startup_arena.engine import GameFactory
from llm_startup_arena.llm import (
    BudgetAllocation,
    CompanyDecision,
    DecisionCoordinator,
)


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, GameState]] = []

    def generate_decision(
        self,
        *,
        model: str,
        company_id: str,
        state: GameState,
    ) -> CompanyDecision:
        self.calls.append((model, company_id, state))
        return CompanyDecision(
            strategy=f"strategy for {company_id}",
            budget=BudgetAllocation(),
        )


def test_coordinator_collects_one_decision_per_company() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    provider = RecordingProvider()

    record = DecisionCoordinator(provider).collect(state)

    assert record.round_number == 1
    assert set(record.decisions) == {company.id for company in state.companies}
    assert [call[0] for call in provider.calls] == list(DEFAULT_MODELS)


def test_coordinator_shares_one_isolated_snapshot() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    provider = RecordingProvider()

    DecisionCoordinator(provider).collect(state)

    snapshots = [call[2] for call in provider.calls]
    assert all(snapshot is snapshots[0] for snapshot in snapshots)
    assert snapshots[0] is not state
    assert snapshots[0] == state


def test_coordinator_reports_decisions_as_they_arrive() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    reported: list[str] = []

    DecisionCoordinator(RecordingProvider()).collect(
        state,
        on_decision=lambda company_id, decision: reported.append(company_id),
    )

    assert reported == [company.id for company in state.companies]
