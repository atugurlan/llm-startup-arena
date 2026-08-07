from llm_startup_arena.config import DEFAULT_MODELS, GameConfig
from llm_startup_arena.engine import GameFactory
from llm_startup_arena.llm.prompts import build_company_prompt


def test_company_prompt_separates_own_and_recruitable_employees() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    prompt = build_company_prompt("nova", state)

    own_heading = "YOUR EMPLOYEE IDS (never recruitment targets):"
    recruitable_heading = "RECRUITABLE EMPLOYEE IDS (the only valid recruitment targets):"
    own_section = prompt.split(own_heading, maxsplit=1)[1].split(recruitable_heading, maxsplit=1)[0]
    recruitable_section = prompt.split(recruitable_heading, maxsplit=1)[1].split(
        "VALID CLIENT IDS:", maxsplit=1
    )[0]

    assert "nova-employee-1" in own_section
    assert "nova-employee-1" not in recruitable_section
    assert "orbit-employee-1" in recruitable_section


def test_company_prompt_explains_budget_and_sabotage_rules() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    prompt = build_company_prompt("nova", state)

    assert "at most 500000" in prompt
    assert "If sabotage budget is 0, sabotage_action must be null" in prompt
    assert "Never put one of YOUR EMPLOYEE IDS" in prompt
