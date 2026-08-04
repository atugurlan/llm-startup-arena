import os

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_MODELS = (
    "qwen3:8b",
    "llama3.1:8b",
    "gemma3:12b",
    "mistral-nemo:12b",
)


class GameConfig(BaseModel):
    """Rules that remain constant throughout a match."""

    model_config = ConfigDict(frozen=True)

    total_rounds: int = Field(default=10, ge=1)
    company_count: int = Field(default=4, ge=2)
    starting_cash: int = Field(default=500_000, ge=0)
    starting_employees: int = Field(default=5, ge=1)
    total_clients: int = Field(default=20, ge=1)


class AppConfig(BaseModel):
    """Runtime configuration loaded from environment variables."""

    model_config = ConfigDict(frozen=True)

    ollama_base_url: str = "http://localhost:11434"
    models: tuple[str, ...] = Field(default=DEFAULT_MODELS, min_length=4, max_length=4)
    game: GameConfig = Field(default_factory=GameConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv()
        models = tuple(
            os.getenv(f"MODEL_COMPANY_{letter}", default)
            for letter, default in zip("ABCD", DEFAULT_MODELS, strict=True)
        )
        game = GameConfig(total_rounds=int(os.getenv("TOTAL_ROUNDS", "10")))
        return cls(
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            models=models,
            game=game,
        )
