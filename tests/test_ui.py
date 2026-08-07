from llm_startup_arena.config import DEFAULT_MODELS, GameConfig
from llm_startup_arena.domain import GameState
from llm_startup_arena.engine import GameFactory
from llm_startup_arena.llm import BudgetAllocation, CompanyDecision, RoundDecisionRecord
from llm_startup_arena.ui.app import round_label, run_next_round
from llm_startup_arena.ui.session import GameSession


class FakeCoordinator:
    def collect(self, state: GameState, on_decision=None) -> RoundDecisionRecord:
        decision = CompanyDecision(strategy="grow", budget=BudgetAllocation())
        if on_decision is not None:
            on_decision("nova", decision)
        return RoundDecisionRecord(
            round_number=state.round_number + 1,
            decisions={"nova": decision},
        )


def build_session() -> GameSession:
    config = GameConfig()
    return GameSession({}, GameFactory(config, DEFAULT_MODELS), config.total_rounds)


def test_round_label_describes_game_progress() -> None:
    state = GameState(companies=[], clients=[])

    assert round_label(state, 10) == "READY FOR ROUND 1 OF 10"
    state.round_number = 4
    assert round_label(state, 10) == "ROUND 4 COMPLETE · NEXT: 5 OF 10"
    state.round_number = 10
    assert round_label(state, 10) == "GAME COMPLETE · 10 ROUNDS"


def test_run_next_round_records_decisions_before_advancing() -> None:
    session = build_session()

    record = run_next_round(session, FakeCoordinator())  # type: ignore[arg-type]

    assert session.state.round_number == 1
    assert session.latest_round is record
