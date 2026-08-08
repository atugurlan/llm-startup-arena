from llm_startup_arena.domain import EmployeeRole, GameState

LOW_MORALE_THRESHOLD = 40
LOW_CASH_THRESHOLD = 100_000

SYSTEM_PROMPT = """
You are the founder and CEO of one company in a competitive startup simulation.
Choose actions that maximize the company's value after ten rounds while keeping it solvent.
Return only a decision matching the supplied JSON schema. The deterministic game engine
calculates all outcomes. Follow every decision rule in the user prompt exactly; a decision
that breaks any rule is rejected and your company is forced to hold with a zero budget.
""".strip()


def build_company_prompt(company_id: str, state: GameState) -> str:
    company = next(company for company in state.companies if company.id == company_id)
    available_clients = [client for client in state.clients if client.company_id is None]
    client_ids = [client.id for client in available_clients]
    client_revenue = {client.id: client.revenue_per_round for client in available_clients}
    candidate_ids = [candidate.id for candidate in state.available_candidates]
    recruitable_employees = [
        {
            **employee.model_dump(mode="json"),
            "current_company": competitor.name,
        }
        for competitor in state.companies
        if competitor.id != company_id
        for employee in competitor.employees
    ]
    recruitable_employee_ids = [employee["id"] for employee in recruitable_employees]
    payroll = sum(employee.salary for employee in company.employees)
    safe_discretionary_budget = max(0, company.cash - payroll)
    standard_budgets = _allowed_budgets(safe_discretionary_budget, 20_000)
    training_budgets = _allowed_budgets(safe_discretionary_budget, 25_000)
    role_power = {
        role.value: sum(
            employee.skill if employee.morale >= LOW_MORALE_THRESHOLD else employee.skill // 2
            for employee in company.employees
            if employee.role == role
        )
        for role in EmployeeRole
    }
    cash_strategy = _build_cash_strategy(company.cash, client_revenue)

    return f"""
You control {company.name!r}, whose company ID is {company_id!r}.
Never mention or act on behalf of another company in your strategy.
All companies decide from the same frozen round snapshot.

{cash_strategy}

STRICT OUTPUT RULES — check every rule before responding:
1. product, marketing, and retention must each be chosen from {standard_budgets}.
2. training must be chosen from {training_budgets}.
3. Total budget must not exceed the safe discretionary budget {safe_discretionary_budget}.
4. target_client_ids must contain 0–2 unique IDs copied only from VALID CLIENT IDS.
5. target_candidate_ids must contain 0–2 unique IDs copied only from AVAILABLE CANDIDATE IDS.
6. target_employee_ids must contain 0–2 unique IDs copied only from RECRUITABLE EMPLOYEE IDS.
7. Recruitment budget is shared across candidate and employee targets.
8. With no recruitment targets, recruitment=0. Otherwise use at least 20000 per total target.
9. recruitment must be chosen from {standard_budgets}.
10. Sabotage is unavailable: sabotage must always be 0 and sabotage_action must be null.
11. Keep strategy short and refer only to {company.name!r}.

PAYROLL OBLIGATION:
- Employee salaries are paid after your decision budget at the end of every round.
- Your payroll this round is {payroll}.
- Your safe discretionary budget after reserving payroll is {safe_discretionary_budget}.
- Prefer a total decision budget at or below {safe_discretionary_budget} to pay salaries.
- If remaining cash cannot cover payroll, cash becomes 0, employee morale drops by 20,
  employee loyalty drops by 15, and company reputation drops by 5.

VALID CLIENT IDS:
{client_ids}

AVAILABLE CANDIDATE IDS:
{candidate_ids}

AVAILABLE CANDIDATE DETAILS:
{[candidate.model_dump(mode="json") for candidate in state.available_candidates]}

RECRUITABLE EMPLOYEE IDS:
{recruitable_employee_ids}

RECRUITABLE EMPLOYEE DETAILS:
{recruitable_employees}

CLIENT ACQUISITION AND REVENUE:
- Only target IDs from VALID CLIENT IDS; clients already under contract are unavailable.
- A targeted available client signs a three-round contract.
- If multiple companies target the same client, the highest product score plus reputation wins.
- Contract revenue is paid every round, including the acquisition round.
- Available client revenue per round: {client_revenue}

EMPLOYEE TRAINING:
- Every 25000 assigned to training gives every current employee +1 skill and +1 experience.
- Skill is capped at 100. Experience has no upper limit.

EMPLOYEE RETENTION:
- Every 20000 assigned to retention gives every current employee +2 morale and +2 loyalty.
- Morale and loyalty are capped at 100.
- An employee with loyalty below 40 after payroll leaves the company at the end of the round.
- Retention is applied before payroll and can prevent an employee from leaving.

EXTERNAL HIRING:
- Candidate IDs currently available: {candidate_ids}
- You may target up to two candidates with target_candidate_ids.
- Recruitment spending is divided equally between your targeted candidates.
- At least 20000 recruitment spending per candidate is required for an eligible offer.
- If you cannot spend that minimum safely, use target_candidate_ids=[] and recruitment=0.
- If companies target the same candidate, personality preferences determine the best offer.
- A hired candidate joins immediately and is included in payroll this round.

COMPETITOR EMPLOYEE RECRUITMENT:
- You may target up to two competitor employees with target_employee_ids.
- Every target must come from RECRUITABLE EMPLOYEE IDS.
- Recruitment budget is split across all external candidate and competitor employee targets.
- Each target needs at least 20000 per target for an eligible offer.
- The offer competes against employee loyalty, current company reputation, and retention.
- A successful transfer moves the employee immediately and updates both companies' payroll.

EMPLOYEE ROLE BONUSES:
- Current effective role power: {role_power}
- Employees with morale below 40 contribute only 50% of their skill to role power.
- With product spending: every 100 engineer power and every 50 product power adds
  +1 product score beyond the base investment gain.
- With marketing spending: every 50 marketing power adds +1 reputation beyond the base gain.
- Every 50 sales power adds +1 to the score used to compete for targeted clients.
- Every 5 operations power reduces payroll by 1%, capped at a 20% discount.
- Training is applied after investments, so new skill affects role bonuses next round.

FINAL SELF-CHECK:
- Every target ID appears in an allowed list above.
- Every budget appears in its allowed budget list above.
- recruitment provides at least 20000 for every candidate and employee target combined.
- sabotage=0 and sabotage_action=null.
- Total budget is at most {safe_discretionary_budget}.

YOUR COMPANY STATE ONLY:
{company.model_dump_json()}
""".strip()


def build_correction_prompt(company_id: str, state: GameState, error: Exception) -> str:
    company = next(company for company in state.companies if company.id == company_id)
    payroll = sum(employee.salary for employee in company.employees)
    safe_budget = max(0, company.cash - payroll)
    available_clients = [client.id for client in state.clients if client.company_id is None]
    available_candidates = [candidate.id for candidate in state.available_candidates]
    recruitable_employees = [
        employee.id
        for competitor in state.companies
        if competitor.id != company_id
        for employee in competitor.employees
    ]
    return f"""
The previous decision for {company.name!r} was invalid: {error}

Return a complete replacement JSON decision using only these constraints:
- product, marketing, retention: {_allowed_budgets(safe_budget, 20_000)}
- training: {_allowed_budgets(safe_budget, 25_000)}
- valid client IDs: {available_clients}
- valid candidate IDs: {available_candidates}
- valid competitor employee IDs: {recruitable_employees}
- recruitment=0 with no targets; otherwise use at least 20000 per candidate and employee target
- sabotage=0 and sabotage_action=null
- total budget <= {safe_budget}
Return JSON only.
""".strip()


def _allowed_budgets(maximum: int, unit: int) -> list[int]:
    return list(range(0, maximum + 1, unit))


def _build_cash_strategy(cash: int, client_revenue: dict[str, int]) -> str:
    if cash >= LOW_CASH_THRESHOLD:
        return "CASH STATUS: Normal. Balance growth spending with payroll and client revenue."

    highest_value_clients = sorted(
        client_revenue,
        key=client_revenue.get,
        reverse=True,
    )[:2]
    return f"""
CRITICAL CASH MODE — available cash is below {LOW_CASH_THRESHOLD}:
- Your primary objective is to increase cash and avoid insolvency.
- Set product=0, marketing=0, training=0, recruitment=0, retention=0, and sabotage=0.
- Set target_candidate_ids=[] and target_employee_ids=[].
- Client targeting costs no money. Target up to two valid high-revenue clients.
- Prefer these currently available high-revenue clients: {highest_value_clients}
- Existing client contracts continue producing revenue automatically.
- Do not spend merely because cash is available; preserve cash for payroll.
""".strip()
