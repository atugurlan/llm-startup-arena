from types import SimpleNamespace
from typing import Any

from llm_startup_arena.domain import Company, GameState
from llm_startup_arena.llm.ollama_provider import OllamaProvider


class FakeOllamaClient:
    def __init__(self) -> None:
        self.request: dict[str, Any] | None = None

    def chat(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        content = """{
            "strategy": "steady growth",
            "budget": {
                "product": 10,
                "marketing": 20,
                "training": 0,
                "recruitment": 0,
                "retention": 0,
                "sabotage": 0
            }
        }"""
        return SimpleNamespace(message=SimpleNamespace(content=content))


def test_provider_returns_validated_decision() -> None:
    client = FakeOllamaClient()
    provider = OllamaProvider(client=client)  # type: ignore[arg-type]
    company = Company(id="nova", name="Nova", model="test-model", cash=100)
    state = GameState(companies=[company], clients=[])

    decision = provider.generate_decision(
        model="test-model",
        company_id="nova",
        state=state,
    )

    assert decision.strategy == "steady growth"
    assert decision.budget.total == 30
    assert client.request is not None
    assert client.request["think"] is False
