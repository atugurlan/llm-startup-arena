import pytest

from llm_startup_arena.config import DEFAULT_MODELS, GameConfig
from llm_startup_arena.engine import GameFactory


def test_factory_creates_complete_initial_state() -> None:
    config = GameConfig()

    state = GameFactory(config, DEFAULT_MODELS).create()

    assert state.round_number == 0
    assert len(state.companies) == 4
    assert len(state.clients) == 20
    assert {company.model for company in state.companies} == set(DEFAULT_MODELS)
    assert {company.cash for company in state.companies} == {config.starting_cash}
    assert {len(company.employees) for company in state.companies} == {config.starting_employees}
    assert all(client.company_id is None for client in state.clients)


def test_factory_is_deterministic() -> None:
    factory = GameFactory(GameConfig(), DEFAULT_MODELS)

    assert factory.create() == factory.create()


def test_factory_rejects_model_count_mismatch() -> None:
    with pytest.raises(ValueError, match="exactly one model"):
        GameFactory(GameConfig(), DEFAULT_MODELS[:3])
