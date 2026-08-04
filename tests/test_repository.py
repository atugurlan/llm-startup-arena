from pathlib import Path

from llm_startup_arena.domain import GameState
from llm_startup_arena.persistence import MatchRepository


def test_repository_round_trip(tmp_path: Path) -> None:
    repository = MatchRepository(tmp_path)
    state = GameState(round_number=3, companies=[], clients=[])

    repository.save_match(state, "example")
    loaded = repository.load_match("example")

    assert loaded == state
    assert repository.list_matches() == [tmp_path / "example.json"]
