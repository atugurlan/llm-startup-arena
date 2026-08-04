from llm_startup_arena.config import DEFAULT_MODELS
from llm_startup_arena.ui.app import build_demo_state


def test_demo_state_uses_selected_model() -> None:
    state = build_demo_state(DEFAULT_MODELS[0])

    assert state.round_number == 1
    assert state.companies[0].model == "qwen3:8b"
    assert state.companies[0].cash == 500_000
