from llm_startup_arena.config import DEFAULT_MODELS, GameConfig
from llm_startup_arena.engine import GameFactory
from llm_startup_arena.llm.prompts import build_company_prompt, build_correction_prompt


def test_company_prompt_lists_recruitable_competitor_employees() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    prompt = build_company_prompt("nova", state)

    assert "RECRUITABLE EMPLOYEE IDS" in prompt
    assert "orbit-employee-1" in prompt
    recruitable_section = prompt.split("RECRUITABLE EMPLOYEE IDS:", maxsplit=1)[1].split(
        "CLIENT ACQUISITION", maxsplit=1
    )[0]
    assert "nova-employee-1" not in recruitable_section
    assert "at least 20000 per target" in prompt


def test_company_prompt_explains_budget_and_sabotage_rules() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    prompt = build_company_prompt("nova", state)

    assert "safe discretionary budget 475000" in prompt
    assert "Sabotage is unavailable" in prompt
    assert "sabotage must always be 0" in prompt
    assert "target_company_id must be null" in prompt
    assert "partnership" not in prompt.casefold()


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
    assert "training must be chosen from" in prompt


def test_company_prompt_explains_retention_formula() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    prompt = build_company_prompt("nova", state)

    assert "Every 20000 assigned to retention" in prompt
    assert "+2 morale and +2 loyalty" in prompt
    assert "retention must each be chosen from" in prompt


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


def test_company_prompt_explains_external_hiring() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()

    prompt = build_company_prompt("nova", state)

    assert "target_candidate_ids" in prompt
    assert "candidate-alex-chen" in prompt
    assert "At least 20000 recruitment spending per candidate" in prompt
    assert "included in payroll this round" in prompt
    assert "Recruitment budget is shared across candidate and employee targets" in prompt
    assert "at least 20000 per total target" in prompt
    assert "You control 'Nova Labs', whose company ID is 'nova'" in prompt
    assert "Never mention or act on behalf of another company" in prompt


def test_company_prompt_does_not_expose_unavailable_clients() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    state.clients[4].company_id = "orbit"
    state.clients[4].contract_rounds_remaining = 2

    prompt = build_company_prompt("nova", state)

    assert "client-5" not in prompt
    assert "CURRENT GAME STATE" not in prompt
    assert "YOUR COMPANY STATE ONLY" in prompt


def test_correction_prompt_repeats_current_allowed_values() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    state.clients[4].company_id = "orbit"

    prompt = build_correction_prompt("nova", state, ValueError("bad decision"))

    assert "bad decision" in prompt
    assert "valid client IDs" in prompt
    assert "client-5" not in prompt
    assert "candidate-alex-chen" in prompt
    assert "valid competitor employee IDs" in prompt
    assert "total budget <= 475000" in prompt


def test_company_prompt_enters_critical_cash_mode_below_threshold() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    state.companies[0].cash = 99_999

    prompt = build_company_prompt("nova", state)

    assert "CRITICAL CASH MODE" in prompt
    assert "increase cash and avoid insolvency" in prompt
    assert "product=0, marketing=0, training=0, recruitment=0, retention=0" in prompt
    assert "Client targeting costs no money" in prompt
    assert "['client-5', 'client-10']" in prompt


def test_company_prompt_uses_normal_cash_strategy_at_threshold() -> None:
    state = GameFactory(GameConfig(), DEFAULT_MODELS).create()
    state.companies[0].cash = 100_000

    prompt = build_company_prompt("nova", state)

    assert "CASH STATUS: Normal" in prompt
    assert "CRITICAL CASH MODE" not in prompt
