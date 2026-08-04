import pytest

from llm_startup_arena.config import DEFAULT_MODELS, GameConfig
from llm_startup_arena.engine import GameFactory
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

    reset_state = session.new_game()

    assert reset_state.round_number == 0
