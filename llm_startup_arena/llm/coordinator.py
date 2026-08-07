from collections.abc import Callable

from llm_startup_arena.domain import GameState

from .provider import CompanyDecision, LLMProvider
from .round_record import RoundDecisionRecord
from .validation import DecisionNormalizer, DecisionValidator


class DecisionCoordinator:
    """Collect one decision per company from a shared round snapshot."""

    def __init__(
        self,
        provider: LLMProvider,
        validator: DecisionValidator | None = None,
        normalizer: DecisionNormalizer | None = None,
    ) -> None:
        self._provider = provider
        self._validator = validator or DecisionValidator()
        self._normalizer = normalizer or DecisionNormalizer()

    def collect(
        self,
        state: GameState,
        on_decision: Callable[[str, CompanyDecision], None] | None = None,
        on_error: Callable[[str, str], None] | None = None,
        on_model_start: Callable[[str], None] | None = None,
    ) -> RoundDecisionRecord:
        snapshot = state.model_copy(deep=True)
        decisions = {}
        errors = {}
        for company in snapshot.companies:
            if on_model_start is not None:
                on_model_start(company.id)
            try:
                decision = self._provider.generate_decision(
                    model=company.model,
                    company_id=company.id,
                    state=snapshot,
                )
                decision = self._normalizer.normalize(
                    company_id=company.id,
                    decision=decision,
                    state=snapshot,
                )
                self._validator.validate(
                    company_id=company.id,
                    decision=decision,
                    state=snapshot,
                )
            # A single provider or validation failure must not stop other companies.
            except Exception as error:  # noqa: BLE001
                message = str(error) or type(error).__name__
                errors[company.id] = message
                if on_error is not None:
                    on_error(company.id, message)
                continue

            decisions[company.id] = decision
            if on_decision is not None:
                on_decision(company.id, decision)

        return RoundDecisionRecord(
            round_number=state.round_number + 1,
            decisions=decisions,
            errors=errors,
        )
