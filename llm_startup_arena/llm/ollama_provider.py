from ollama import Client
from pydantic import ValidationError

from llm_startup_arena.domain import GameState

from .prompts import SYSTEM_PROMPT, build_company_prompt, build_correction_prompt
from .provider import CompanyDecision
from .validation import DecisionNormalizer, DecisionValidationError, DecisionValidator

DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_OUTPUT_TOKENS = 700
MAX_DECISION_ATTEMPTS = 3
CORRECTION_TEMPERATURE = 0.1


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
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_company_prompt(company_id, state)},
        ]
        last_error: ValueError | ValidationError | None = None

        for attempt in range(MAX_DECISION_ATTEMPTS):
            response = self.client.chat(
                model=model,
                messages=messages,
                format=CompanyDecision.model_json_schema(),
                think=False,
                options={
                    "temperature": (self.temperature if attempt == 0 else CORRECTION_TEMPERATURE),
                    "num_predict": self.max_output_tokens,
                },
                keep_alive=0,
            )
            content = response.message.content
            try:
                if not content or not content.strip():
                    raise ValueError(f"Model {model!r} returned an empty decision")
                decision = CompanyDecision.model_validate_json(content)
                decision = DecisionNormalizer().normalize(
                    company_id=company_id,
                    decision=decision,
                    state=state,
                )
                return DecisionValidator().validate(
                    company_id=company_id,
                    decision=decision,
                    state=state,
                )
            except (DecisionValidationError, ValidationError, ValueError) as error:
                last_error = error
                if attempt == MAX_DECISION_ATTEMPTS - 1:
                    break
                messages.extend(
                    [
                        {"role": "assistant", "content": content or ""},
                        {
                            "role": "user",
                            "content": build_correction_prompt(company_id, state, error),
                        },
                    ]
                )

        assert last_error is not None
        raise ValueError(
            f"Decision rejected after {MAX_DECISION_ATTEMPTS} attempts: {last_error}"
        ) from last_error
