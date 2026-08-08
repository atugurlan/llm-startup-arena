from types import SimpleNamespace
from typing import Any

import pytest

from llm_startup_arena.domain import Company, GameState
from llm_startup_arena.llm.ollama_provider import OllamaProvider


class FakeOllamaClient:
    def __init__(self) -> None:
        self.request: dict[str, Any] | None = None
        self.requests: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        self.requests.append(kwargs)
        content = """{
            "strategy": "steady growth",
            "budget": {
                "product": 20000,
                "marketing": 20000,
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
    company = Company(id="nova", name="Nova", model="test-model", cash=100_000)
    state = GameState(companies=[company], clients=[])

    decision = provider.generate_decision(
        model="test-model",
        company_id="nova",
        state=state,
    )

    assert decision.strategy == "steady growth"
    assert decision.budget.total == 40_000
    assert client.request is not None
    assert client.request["think"] is False
    assert "partnership_offer" not in client.request["format"]["properties"]


class RetryingOllamaClient(FakeOllamaClient):
    def chat(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        self.requests.append(kwargs)
        product = 120_000 if len(self.requests) == 1 else 20_000
        content = f"""{{
            "strategy": "protect the team",
            "budget": {{
                "product": {product},
                "marketing": 0,
                "training": 0,
                "recruitment": 0,
                "retention": 0,
                "sabotage": 0
            }}
        }}"""
        return SimpleNamespace(message=SimpleNamespace(content=content))


def test_provider_retries_once_with_validation_feedback() -> None:
    client = RetryingOllamaClient()
    provider = OllamaProvider(client=client)  # type: ignore[arg-type]
    company = Company(id="nova", name="Nova", model="test-model", cash=100_000)
    state = GameState(companies=[company], clients=[])

    decision = provider.generate_decision(
        model="test-model",
        company_id="nova",
        state=state,
    )

    assert decision.budget.product == 20_000
    assert len(client.requests) == 2
    retry_message = client.requests[1]["messages"][-1]["content"]
    assert "exceeds available cash" in retry_message
    assert "Return a complete replacement JSON decision" in retry_message
    assert "sabotage=0 and sabotage_action=null" in retry_message
    assert client.requests[1]["options"]["temperature"] == 0.1


class AlwaysInvalidOllamaClient(FakeOllamaClient):
    def chat(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        self.requests.append(kwargs)
        content = """{
            "strategy": "invalid forever",
            "budget": {
                "product": 120000,
                "marketing": 0,
                "training": 0,
                "recruitment": 0,
                "retention": 0,
                "sabotage": 0
            }
        }"""
        return SimpleNamespace(message=SimpleNamespace(content=content))


def test_provider_rejects_decision_after_three_invalid_attempts() -> None:
    client = AlwaysInvalidOllamaClient()
    provider = OllamaProvider(client=client)  # type: ignore[arg-type]
    company = Company(id="nova", name="Nova", model="test-model", cash=100_000)
    state = GameState(companies=[company], clients=[])

    with pytest.raises(ValueError, match="Decision rejected after 3 attempts"):
        provider.generate_decision(
            model="test-model",
            company_id="nova",
            state=state,
        )

    assert len(client.requests) == 3
    assert client.requests[0]["options"]["temperature"] == provider.temperature
    assert client.requests[1]["options"]["temperature"] == 0.1
    assert client.requests[2]["options"]["temperature"] == 0.1
