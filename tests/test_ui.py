from llm_startup_arena.config import DEFAULT_MODELS
from llm_startup_arena.domain import GameState
from llm_startup_arena.ui.app import build_demo_state, round_label


def test_demo_state_uses_selected_model() -> None:
    state = build_demo_state(DEFAULT_MODELS[0])

    assert state.round_number == 1
    assert state.companies[0].model == "qwen3:8b"
    assert state.companies[0].cash == 500_000


def test_round_label_describes_game_progress() -> None:
    state = GameState(companies=[], clients=[])

    assert round_label(state, 10) == "READY FOR ROUND 1 OF 10"
    state.round_number = 4
    assert round_label(state, 10) == "ROUND 4 COMPLETE · NEXT: 5 OF 10"
    state.round_number = 10
    assert round_label(state, 10) == "GAME COMPLETE · 10 ROUNDS"
