from llm_startup_arena.domain import Company, GameState
from llm_startup_arena.engine import Arena
from llm_startup_arena.llm.provider import BudgetAllocation, CompanyDecision


class FakeProvider:
    def generate_decision(
        self,
        *,
        model: str,
        company_id: str,
        state: GameState,
    ) -> CompanyDecision:
        return CompanyDecision(strategy="Hold", budget=BudgetAllocation())


def test_new_arena_is_not_finished() -> None:
    arena = Arena(GameState(companies=[], clients=[]))

    assert arena.is_finished is False


def test_arena_finishes_after_ten_rounds() -> None:
    arena = Arena(GameState(round_number=10, companies=[], clients=[]))

    assert arena.is_finished is True


def test_run_round_collects_decisions_from_the_shared_snapshot() -> None:
    company = Company(id="nova", name="Nova", model="test-model", cash=500_000)
    arena = Arena(GameState(companies=[company], clients=[]), provider=FakeProvider())

    decisions = arena.run_round()

    assert decisions["nova"].strategy == "Hold"
    assert arena.state.round_number == 1
