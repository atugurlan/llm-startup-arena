from collections.abc import MutableMapping
from typing import Any

from llm_startup_arena.domain import GameState
from llm_startup_arena.engine import GameFactory
from llm_startup_arena.llm import RoundDecisionRecord

GAME_STATE_KEY = "game_state"
ROUND_HISTORY_KEY = "round_history"


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

    @property
    def round_history(self) -> list[RoundDecisionRecord]:
        stored_history = self._storage.get(ROUND_HISTORY_KEY)
        if not isinstance(stored_history, list) or not all(
            isinstance(record, RoundDecisionRecord) for record in stored_history
        ):
            stored_history = []
            self._storage[ROUND_HISTORY_KEY] = stored_history
        return stored_history

    @property
    def latest_round(self) -> RoundDecisionRecord | None:
        return self.round_history[-1] if self.round_history else None

    def new_game(self) -> GameState:
        state = self._factory.create()
        self._storage[GAME_STATE_KEY] = state
        self._storage[ROUND_HISTORY_KEY] = []
        return state

    def record_round(self, record: RoundDecisionRecord) -> None:
        if any(existing.round_number == record.round_number for existing in self.round_history):
            raise ValueError(f"Round {record.round_number} has already been recorded")
        self.round_history.append(record)

    def advance_round(self) -> GameState:
        if self.is_finished:
            raise RuntimeError("The game has already finished")

        state = self.state.model_copy(deep=True)
        state.round_number += 1
        self._storage[GAME_STATE_KEY] = state
        return state
