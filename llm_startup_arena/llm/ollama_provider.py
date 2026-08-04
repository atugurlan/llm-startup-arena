from ollama import Client

from llm_startup_arena.domain import GameState

from .prompts import SYSTEM_PROMPT, build_company_prompt
from .provider import CompanyDecision

DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_OUTPUT_TOKENS = 700


class OllamaProvider:
    """Generate and validate company decisions with a local Ollama server."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        *,
        temperature: float = DEFAULT_TEMPERATURE,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        client: Client | None = None,
    ) -> None:
        self.client = client or Client(host=base_url)
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def generate_decision(
        self,
        *,
        model: str,
        company_id: str,
        state: GameState,
    ) -> CompanyDecision:
        response = self.client.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_company_prompt(company_id, state.model_dump_json()),
                },
            ],
            format=CompanyDecision.model_json_schema(),
            think=False,
            options={
                "temperature": self.temperature,
                "num_predict": self.max_output_tokens,
            },
            keep_alive=0,
        )

        content = response.message.content
        if not content or not content.strip():
            raise ValueError(f"Model {model!r} returned an empty decision")

        return CompanyDecision.model_validate_json(content)
