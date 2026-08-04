from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from llm_startup_arena.domain import GameState


class MatchRepository:
    """Store match snapshots as human-readable JSON files."""

    def __init__(self, directory: Path | str = "matches") -> None:
        self.directory = Path(directory)

    def save_match(self, state: GameState, match_id: str | None = None) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        identifier = match_id or self.new_match_id()
        path = self._path_for(identifier)
        path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load_match(self, match_id: str) -> GameState:
        return GameState.model_validate_json(self._path_for(match_id).read_text(encoding="utf-8"))

    def list_matches(self) -> list[Path]:
        if not self.directory.exists():
            return []
        return sorted(self.directory.glob("*.json"), key=lambda path: path.stat().st_mtime)

    def new_match_id(self) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return f"match-{timestamp}-{uuid4().hex[:8]}"

    def _path_for(self, match_id: str) -> Path:
        if not match_id or Path(match_id).name != match_id:
            raise ValueError("match_id must be a plain file identifier")
        return self.directory / f"{match_id}.json"
