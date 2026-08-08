import pytest

from llm_startup_arena.config import DEFAULT_MODELS, GameConfig
from llm_startup_arena.domain import GameState
from llm_startup_arena.engine import GameFactory, RoundResolver
from llm_startup_arena.llm import (
    BudgetAllocation,
    CompanyDecision,
    RoundDecisionRecord,
    SabotageAction,
)
from llm_startup_arena.ui.app import (
    employee_roster_rows,
    render_decision,
    round_label,
    run_next_round,
)
from llm_startup_arena.ui.session import GameSession


class FakeCoordinator:
    def collect(
        self,
        state: GameState,
        on_decision=None,
        on_error=None,
        on_model_start=None,
    ) -> RoundDecisionRecord:
        decision = CompanyDecision(strategy="grow", budget=BudgetAllocation())
        if on_model_start is not None:
            on_model_start("nova")
        if on_decision is not None:
            on_decision("nova", decision)
        return RoundDecisionRecord(
            round_number=state.round_number + 1,
            decisions={"nova": decision},
        )


class FailedCoordinator:
    def collect(self, state: GameState, **kwargs) -> RoundDecisionRecord:
        return RoundDecisionRecord(
            round_number=state.round_number + 1,
            errors={company.id: "failed" for company in state.companies},
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

    record = run_next_round(
        session,
        FakeCoordinator(),  # type: ignore[arg-type]
        RoundResolver(),
    )

    assert session.state.round_number == 1
    assert session.latest_round is record


def test_run_next_round_does_not_advance_when_all_models_fail() -> None:
    session = build_session()

    with pytest.raises(ValueError, match="All four models failed"):
        run_next_round(
            session,
            FailedCoordinator(),  # type: ignore[arg-type]
            RoundResolver(),
        )

    assert session.state.round_number == 0
    assert session.round_history == []


def test_employee_roster_rows_reflect_current_company_ownership() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    transferred = state.companies[1].employees.pop(0)
    state.companies[0].employees.append(transferred)

    rows = employee_roster_rows(state)
    transferred_row = next(row for row in rows if row["Employee"] == transferred.name)

    assert len(rows) == 20
    assert transferred_row == {
        "Company": "Nova Labs",
        "Employee": "Orbit Employee 1",
        "Role": "Engineer",
        "Personality": "Ambitious",
        "Skill": 50,
        "Morale": 70,
        "Loyalty": 65,
        "Salary / round": "$4,000",
    }


def test_decision_card_shows_sabotage_action_and_company_name() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    rendered: list[str] = []

    class FakeSlot:
        def markdown(self, content: str, **kwargs) -> None:
            rendered.append(content)

    decision = CompanyDecision(
        strategy="weaken the market leader",
        budget=BudgetAllocation(sabotage=20_000),
        sabotage_action=SabotageAction.REPUTATION_ATTACK,
        target_company_id="orbit",
    )

    render_decision(
        FakeSlot(),  # type: ignore[arg-type]
        decision,
        companies={company.id: company for company in state.companies},
    )

    assert "Sabotage: reputation_attack" in rendered[0]
    assert "Target: Orbit AI" in rendered[0]
