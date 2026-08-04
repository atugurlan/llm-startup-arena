from collections.abc import MutableMapping
from typing import Any

from llm_startup_arena.domain import GameState
from llm_startup_arena.engine import GameFactory

GAME_STATE_KEY = "game_state"


class GameSession:
    """Manage a game state inside Streamlit-compatible session storage."""

    def __init__(
        self,
        storage: MutableMapping[str, Any],
        factory: GameFactory,
        total_rounds: int,
    ) -> None:
        self._storage = storage
        self._factory = factory
        self._total_rounds = total_rounds

    @property
    def state(self) -> GameState:
        stored_state = self._storage.get(GAME_STATE_KEY)
        if not isinstance(stored_state, GameState):
            stored_state = self._factory.create()
            self._storage[GAME_STATE_KEY] = stored_state
        return stored_state

    @property
    def is_finished(self) -> bool:
        return self.state.round_number >= self._total_rounds

    def new_game(self) -> GameState:
        state = self._factory.create()
        self._storage[GAME_STATE_KEY] = state
        return state

    def advance_round(self) -> GameState:
        if self.is_finished:
            raise RuntimeError("The game has already finished")

        state = self.state.model_copy(deep=True)
        state.round_number += 1
        self._storage[GAME_STATE_KEY] = state
        return state
