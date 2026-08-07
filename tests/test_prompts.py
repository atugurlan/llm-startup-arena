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


def test_company_prompt_explains_payroll_reserve_and_penalties() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    prompt = build_company_prompt("nova", state)

    assert "Your payroll this round is 25000" in prompt
    assert "safe discretionary budget after reserving payroll is 475000" in prompt
    assert "employee morale drops by 20" in prompt
    assert "employee loyalty drops by 15" in prompt
    assert "company reputation drops by 5" in prompt


def test_company_prompt_explains_client_contracts_and_revenue() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    prompt = build_company_prompt("nova", state)

    assert "signs a three-round contract" in prompt
    assert "product score plus reputation wins" in prompt
    assert "including the acquisition round" in prompt
    assert "'client-1': 8000" in prompt


def test_company_prompt_explains_training_formula() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    prompt = build_company_prompt("nova", state)

    assert "Every 25000 assigned to training" in prompt
    assert "+1 skill and +1 experience" in prompt
    assert "Training amounts below 25000" in prompt


def test_company_prompt_explains_retention_formula() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    prompt = build_company_prompt("nova", state)

    assert "Every 20000 assigned to retention" in prompt
    assert "+2 morale and +2 loyalty" in prompt
    assert "Retention amounts below 20000" in prompt


def test_company_prompt_explains_role_power_and_bonuses() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    prompt = build_company_prompt("nova", state)

    assert "Current effective role power" in prompt
    assert "'engineer': 107" in prompt
    assert "every 100 engineer power" in prompt
    assert "Every 50 sales power" in prompt
    assert "operations power reduces payroll" in prompt


def test_company_prompt_explains_morale_and_departure_rules() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    prompt = build_company_prompt("nova", state)

    assert "morale below 40 contribute only 50%" in prompt
    assert "loyalty below 40 after payroll leaves" in prompt
    assert "Retention is applied before payroll" in prompt
