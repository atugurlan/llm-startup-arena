from llm_startup_arena.config import DEFAULT_MODELS, AppConfig
from llm_startup_arena.ui.app import build_arena_state, build_demo_state


def test_demo_state_uses_selected_model() -> None:
    state = build_demo_state(DEFAULT_MODELS[0])

    assert state.round_number == 1
    assert state.companies[0].model == "qwen3:8b"
    assert state.companies[0].cash == 500_000


def test_arena_state_starts_companies_equally() -> None:
    state = build_arena_state(AppConfig())

    assert len(state.companies) == 4
    assert {company.model for company in state.companies} == set(DEFAULT_MODELS)
    assert {company.cash for company in state.companies} == {500_000}
    assert {len(company.employees) for company in state.companies} == {5}
