from llm_startup_arena.domain import EmployeeRole, GameState

SYSTEM_PROMPT = """
You are the founder and CEO of one company in a competitive startup simulation.
Choose actions that maximize the company's value after ten rounds while keeping it solvent.
Return only a decision matching the supplied JSON schema. The deterministic game engine
calculates all outcomes. Follow every decision rule in the user prompt exactly; a decision
that breaks any rule is rejected and your company is forced to hold with a zero budget.
""".strip()


def build_company_prompt(company_id: str, state: GameState) -> str:
    company = next(company for company in state.companies if company.id == company_id)
    own_employee_ids = [employee.id for employee in company.employees]
    recruitable_employee_ids = [
        employee.id
        for competitor in state.companies
        if competitor.id != company_id
        for employee in competitor.employees
    ]
    available_clients = [client for client in state.clients if client.company_id is None]
    client_ids = [client.id for client in available_clients]
    client_revenue = {client.id: client.revenue_per_round for client in available_clients}
    payroll = sum(employee.salary for employee in company.employees)
    safe_discretionary_budget = max(0, company.cash - payroll)
    role_power = {
        role.value: sum(employee.skill for employee in company.employees if employee.role == role)
        for role in EmployeeRole
    }

    return f"""
You control company {company_id!r}.
All companies decide from the same frozen round snapshot.

DECISION RULES — violating any rule rejects the entire decision:
1. Every budget value must be a non-negative integer.
2. Total budget across all six categories must be at most {company.cash}.
3. target_client_ids must contain 0–2 unique IDs selected only from VALID CLIENT IDS.
4. target_employee_ids is only for recruiting employees from competing companies. It must
   contain 0–2 unique IDs selected only from RECRUITABLE EMPLOYEE IDS.
5. Never put one of YOUR EMPLOYEE IDS in target_employee_ids. Retention spending does not
   require employee targets; use an empty target_employee_ids list when not recruiting.
6. If sabotage budget is 0, sabotage_action must be null.
7. If sabotage budget is greater than 0, sabotage_action must be a non-empty description.
8. Use [] for unused target lists and null for unused optional actions or offers.
9. Keep strategy short and descriptive.

PAYROLL OBLIGATION:
- Employee salaries are paid after your decision budget at the end of every round.
- Your payroll this round is {payroll}.
- Your safe discretionary budget after reserving payroll is {safe_discretionary_budget}.
- Prefer a total decision budget at or below {safe_discretionary_budget} to pay salaries.
- If remaining cash cannot cover payroll, cash becomes 0, employee morale drops by 20,
  employee loyalty drops by 10, and company reputation drops by 5.

YOUR EMPLOYEE IDS (never recruitment targets):
{own_employee_ids}

RECRUITABLE EMPLOYEE IDS (the only valid recruitment targets):
{recruitable_employee_ids}

VALID CLIENT IDS:
{client_ids}

CLIENT ACQUISITION AND REVENUE:
- Only target IDs from VALID CLIENT IDS; clients already under contract are unavailable.
- A targeted available client signs a three-round contract.
- If multiple companies target the same client, the highest product score plus reputation wins.
- Contract revenue is paid every round, including the acquisition round.
- Available client revenue per round: {client_revenue}

EMPLOYEE TRAINING:
- Every 25000 assigned to training gives every current employee +1 skill and +1 experience.
- Skill is capped at 100. Experience has no upper limit.
- Training amounts below 25000 are still spent but do not produce a level.

EMPLOYEE RETENTION:
- Every 20000 assigned to retention gives every current employee +2 morale and +2 loyalty.
- Morale and loyalty are capped at 100.
- Retention amounts below 20000 are still spent but do not produce an increase.

EMPLOYEE ROLE BONUSES:
- Current role power (sum of skill by role): {role_power}
- With product spending: every 100 engineer power and every 50 product power adds
  +1 product score beyond the base investment gain.
- With marketing spending: every 50 marketing power adds +1 reputation beyond the base gain.
- Every 50 sales power adds +1 to the score used to compete for targeted clients.
- Every 5 operations power reduces payroll by 1%, capped at a 20% discount.
- Training is applied after investments, so new skill affects role bonuses next round.

Example of consistent unused fields:
target_employee_ids=[], target_client_ids=[], sabotage_action=null, partnership_offer=null

CURRENT GAME STATE:
{state.model_dump_json()}
""".strip()
