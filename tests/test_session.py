import pytest

from llm_startup_arena.config import DEFAULT_MODELS, GameConfig
from llm_startup_arena.engine import GameFactory, RoundResolver
from llm_startup_arena.llm import BudgetAllocation, CompanyDecision, RoundDecisionRecord
from llm_startup_arena.ui.session import GameSession


def build_session(storage: dict | None = None) -> GameSession:
    config = GameConfig()
    return GameSession(
        storage if storage is not None else {},
        GameFactory(config, DEFAULT_MODELS),
        config.total_rounds,
    )


def test_session_initializes_game_once() -> None:
    storage = {}
    session = build_session(storage)

    initial_state = session.state

    assert session.state is initial_state
    assert storage["game_state"] is initial_state


def test_session_captures_initial_company_snapshot() -> None:
    session = build_session()

    history = session.snapshot_history

    assert len(history) == 1
    assert history[0].round_number == 0
    assert len(history[0].companies) == 4
    nova = history[0].companies[0]
    assert nova.company_id == "nova"
    assert nova.cash == 500_000
    assert nova.product_score == 20
    assert nova.reputation == 50
    assert nova.employee_count == 5
    assert nova.client_count == 0


def test_session_advances_without_mutating_previous_state() -> None:
    session = build_session()
    initial_state = session.state

    advanced_state = session.advance_round()

    assert initial_state.round_number == 0
    assert advanced_state.round_number == 1


def test_session_stops_after_final_round() -> None:
    session = build_session()

    for _ in range(10):
        session.advance_round()

    assert session.is_finished is True
    with pytest.raises(RuntimeError, match="already finished"):
        session.advance_round()


def test_new_game_resets_progress() -> None:
    session = build_session()
    session.advance_round()
    session.record_round(build_round_record(1))

    reset_state = session.new_game()

    assert reset_state.round_number == 0
    assert session.round_history == []
    assert [snapshot.round_number for snapshot in session.snapshot_history] == [0]


def build_round_record(round_number: int) -> RoundDecisionRecord:
    decision = CompanyDecision(strategy="grow", budget=BudgetAllocation(product=10))
    return RoundDecisionRecord(round_number=round_number, decisions={"nova": decision})


def test_session_records_round_history_in_order() -> None:
    session = build_session()

    session.record_round(build_round_record(1))
    session.record_round(build_round_record(2))

    assert [record.round_number for record in session.round_history] == [1, 2]
    assert session.latest_round == session.round_history[-1]


def test_session_rejects_duplicate_round_record() -> None:
    session = build_session()
    session.record_round(build_round_record(1))

    with pytest.raises(ValueError, match="already been recorded"):
        session.record_round(build_round_record(1))


def test_session_resolves_and_records_round_atomically() -> None:
    session = build_session()
    decision = CompanyDecision(
        strategy="invest",
        budget=BudgetAllocation(product=100_000),
    )
    record = RoundDecisionRecord(round_number=1, decisions={"nova": decision})

    resolved = session.resolve_round(record, RoundResolver())

    assert resolved.round_number == 1
    assert resolved.companies[0].cash == 375_000
    assert resolved.companies[0].product_score == 27
    assert session.latest_round is record


def test_session_stores_independent_snapshot_after_resolved_round() -> None:
    session = build_session()
    initial_snapshot = session.snapshot_history[0]
    decision = CompanyDecision(
        strategy="invest",
        budget=BudgetAllocation(product=100_000),
    )
    record = RoundDecisionRecord(round_number=1, decisions={"nova": decision})

    session.resolve_round(record, RoundResolver())

    assert [snapshot.round_number for snapshot in session.snapshot_history] == [0, 1]
    assert initial_snapshot.companies[0].cash == 500_000
    assert initial_snapshot.companies[0].product_score == 20
    latest_nova = session.snapshot_history[-1].companies[0]
    assert latest_nova.cash == 375_000
    assert latest_nova.product_score == 27
