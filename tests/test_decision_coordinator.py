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


class OverspendingProvider:
    def generate_decision(
        self,
        *,
        model: str,
        company_id: str,
        state: GameState,
    ) -> CompanyDecision:
        return CompanyDecision(
            strategy="spend everything",
            budget=BudgetAllocation(product=state.companies[0].cash + 1),
        )


class PartiallyFailingProvider(RecordingProvider):
    def generate_decision(
        self,
        *,
        model: str,
        company_id: str,
        state: GameState,
    ) -> CompanyDecision:
        if company_id == "orbit":
            raise RuntimeError("model unavailable")
        return super().generate_decision(
            model=model,
            company_id=company_id,
            state=state,
        )


class RecoverableMistakeProvider:
    def generate_decision(
        self,
        *,
        model: str,
        company_id: str,
        state: GameState,
    ) -> CompanyDecision:
        return CompanyDecision(
            strategy="recover invalid targets",
            budget=BudgetAllocation(),
            target_client_ids=["missing-client"],
            target_employee_ids=[f"{company_id}-employee-1"],
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


def test_coordinator_records_invalid_decision_as_error() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    reported: list[str] = []
    rejected: list[str] = []

    record = DecisionCoordinator(OverspendingProvider()).collect(
        state,
        on_decision=lambda company_id, decision: reported.append(company_id),
        on_error=lambda company_id, message: rejected.append(company_id),
    )

    assert reported == []
    assert rejected == [company.id for company in state.companies]
    assert set(record.errors) == set(rejected)
    assert all("exceeds available cash" in message for message in record.errors.values())


def test_coordinator_continues_after_model_failure() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    started: list[str] = []

    record = DecisionCoordinator(PartiallyFailingProvider()).collect(
        state,
        on_model_start=started.append,
    )

    assert started == [company.id for company in state.companies]
    assert set(record.decisions) == {"nova", "pixel", "apex"}
    assert record.errors == {"orbit": "model unavailable"}


def test_coordinator_normalizes_recoverable_mistakes() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    record = DecisionCoordinator(RecoverableMistakeProvider()).collect(state)

    assert record.errors == {}
    assert set(record.decisions) == {company.id for company in state.companies}
    for decision in record.decisions.values():
        assert decision.target_client_ids == []
        assert decision.target_employee_ids == []
        assert decision.budget.sabotage == 0
        assert decision.sabotage_action is None
        assert decision.target_company_id is None
