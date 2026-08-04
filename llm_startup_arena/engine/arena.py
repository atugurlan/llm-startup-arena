from llm_startup_arena.config import GameConfig
from llm_startup_arena.domain import GameState
from llm_startup_arena.llm.provider import CompanyDecision, LLMProvider
from llm_startup_arena.persistence import MatchRepository

from .resolver import RoundResolver


class Arena:
    """Coordinates rounds without embedding provider-specific LLM logic."""

    def __init__(
        self,
        state: GameState,
        config: GameConfig | None = None,
        provider: LLMProvider | None = None,
        resolver: RoundResolver | None = None,
        repository: MatchRepository | None = None,
    ) -> None:
        self.state = state
        self.config = config or GameConfig()
        self.provider = provider
        self.resolver = resolver or RoundResolver()
        self.repository = repository

    @property
    def is_finished(self) -> bool:
        return self.state.round_number >= self.config.total_rounds

    def run_round(self) -> dict[str, CompanyDecision]:
        self._ensure_round_can_run()
        snapshot = self.state.model_copy(deep=True)
        decisions = self._collect_decisions(snapshot)
        self.state = self.resolver.resolve_round(snapshot, decisions)
        self._save_state()
        return decisions

    def run_game(self) -> GameState:
        while not self.is_finished:
            self.run_round()
        return self.state

    def _collect_decisions(self, snapshot: GameState) -> dict[str, CompanyDecision]:
        assert self.provider is not None
        return {
            company.id: self.provider.generate_decision(
                model=company.model,
                company_id=company.id,
                state=snapshot,
            )
            for company in snapshot.companies
        }

    def _ensure_round_can_run(self) -> None:
        if self.is_finished:
            raise RuntimeError("The game has already finished")
        if self.provider is None:
            raise RuntimeError("An LLM provider is required to run a round")

    def _save_state(self) -> None:
        if self.repository is not None:
            self.repository.save_match(self.state)
