from collections.abc import Mapping

from llm_startup_arena.domain import Company, Employee, EmployeePersonality, EmployeeRole, GameState
from llm_startup_arena.llm.provider import BudgetAllocation, CompanyDecision

INVESTMENT_PER_SCORE_POINT = 20_000
UNPAID_PAYROLL_MORALE_PENALTY = 20
UNPAID_PAYROLL_LOYALTY_PENALTY = 15
UNPAID_PAYROLL_REPUTATION_PENALTY = 5
CLIENT_CONTRACT_ROUNDS = 3
TRAINING_COST_PER_LEVEL = 25_000
RETENTION_COST_PER_LEVEL = 20_000
RETENTION_POINTS_PER_LEVEL = 2
ENGINEERING_POWER_PER_PRODUCT_POINT = 100
PRODUCT_POWER_PER_PRODUCT_POINT = 50
MARKETING_POWER_PER_REPUTATION_POINT = 50
SALES_POWER_PER_ACQUISITION_POINT = 50
OPERATIONS_POWER_PER_PAYROLL_PERCENT = 5
MAX_PAYROLL_DISCOUNT_PERCENT = 20
MIN_RECRUITMENT_BUDGET_PER_CANDIDATE = 20_000
LOW_MORALE_THRESHOLD = 40
LOW_MORALE_POWER_PERCENT = 50
DEPARTURE_LOYALTY_THRESHOLD = 40
_HOLD_DECISION = CompanyDecision(strategy="hold", budget=BudgetAllocation())


class RoundResolver:
    """Apply decisions to a frozen snapshot through deterministic rule stages."""

    def resolve_round(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        resolved = state.model_copy(deep=True)
        resolved.last_round_events = {}
        resolved = self.resolve_investments(resolved, decisions)
        resolved = self.resolve_training(resolved, decisions)
        resolved = self.resolve_retention(resolved, decisions)
        resolved = self.resolve_recruitment(resolved, decisions)
        resolved = self.resolve_clients(resolved, decisions)
        resolved = self.resolve_sabotage(resolved, decisions)
        resolved = self.process_payroll(resolved)
        resolved = self.resolve_departures(resolved)
        for company in resolved.companies:
            _record_event(resolved, company.id, f"Round-end cash: ${company.cash:,}.")
        resolved.round_number += 1
        return resolved

    def resolve_investments(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        resolved = state.model_copy(deep=True)
        for company in resolved.companies:
            decision = decisions.get(company.id)
            if decision is None:
                continue

            total_budget = decision.budget.total
            if total_budget > company.cash:
                raise ValueError(
                    f"Company {company.id!r} cannot spend {total_budget}; "
                    f"only {company.cash} is available"
                )

            company.cash -= total_budget
            if total_budget > 0:
                _record_event(resolved, company.id, f"Total budget spent: ${total_budget:,}.")

            product_gain = decision.budget.product // INVESTMENT_PER_SCORE_POINT
            product_bonus = _product_role_bonus(company, decision)
            company.product_score = min(
                100,
                company.product_score + product_gain + product_bonus,
            )
            if decision.budget.product > 0:
                _record_event(
                    resolved,
                    company.id,
                    f"Product: +{product_gain} investment, +{product_bonus} role bonus.",
                )

            reputation_gain = decision.budget.marketing // INVESTMENT_PER_SCORE_POINT
            reputation_bonus = _marketing_role_bonus(company, decision)
            company.reputation = min(
                100,
                company.reputation + reputation_gain + reputation_bonus,
            )
            if decision.budget.marketing > 0:
                _record_event(
                    resolved,
                    company.id,
                    f"Reputation: +{reputation_gain} investment, +{reputation_bonus} role bonus.",
                )
        return resolved

    def resolve_training(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        resolved = state.model_copy(deep=True)
        for company in resolved.companies:
            decision = decisions.get(company.id)
            if decision is None:
                continue
            training_levels = decision.budget.training // TRAINING_COST_PER_LEVEL
            for employee in company.employees:
                employee.skill = min(100, employee.skill + training_levels)
                employee.experience += training_levels
            if training_levels > 0:
                _record_event(
                    resolved,
                    company.id,
                    f"Training: {len(company.employees)} employees gained "
                    f"+{training_levels} skill and experience.",
                )
        return resolved

    def resolve_recruitment(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        resolved = state.model_copy(deep=True)
        companies = {company.id: company for company in resolved.companies}

        for candidate in list(resolved.available_candidates):
            offers = []
            for company in resolved.companies:
                decision = decisions.get(company.id)
                if decision is None or candidate.id not in decision.target_candidate_ids:
                    continue
                budget_per_candidate = decision.budget.recruitment // _recruitment_target_count(
                    decision
                )
                if budget_per_candidate < MIN_RECRUITMENT_BUDGET_PER_CANDIDATE:
                    continue
                offers.append(
                    (
                        _candidate_offer_score(company, candidate, decision, budget_per_candidate),
                        company,
                    )
                )

            if not offers:
                continue

            _, winner = max(offers, key=lambda offer: offer[0])
            winner.employees.append(candidate)
            resolved.available_candidates.remove(candidate)
            _record_event(
                resolved,
                winner.id,
                f"Hired {candidate.name} ({candidate.role.value}, {candidate.personality.value}).",
            )

        for company_id, decision in decisions.items():
            if not decision.target_candidate_ids:
                continue
            hired_ids = {employee.id for employee in companies[company_id].employees}
            if not any(candidate_id in hired_ids for candidate_id in decision.target_candidate_ids):
                _record_event(resolved, company_id, "Hiring: no external offer was accepted.")

        employee_owners = {
            employee.id: company for company in resolved.companies for employee in company.employees
        }
        transferred_employee_ids: dict[str, set[str]] = {}
        for employee_id, owner in list(employee_owners.items()):
            employee = next(employee for employee in owner.employees if employee.id == employee_id)
            offers = []
            for company in resolved.companies:
                decision = decisions.get(company.id)
                if (
                    decision is None
                    or company.id == owner.id
                    or employee_id not in decision.target_employee_ids
                ):
                    continue
                budget_per_target = decision.budget.recruitment // _recruitment_target_count(
                    decision
                )
                if budget_per_target < MIN_RECRUITMENT_BUDGET_PER_CANDIDATE:
                    continue
                offers.append(
                    (
                        _candidate_offer_score(
                            company,
                            employee,
                            decision,
                            budget_per_target,
                        ),
                        company,
                    )
                )

            if not offers:
                continue

            best_score, winner = max(offers, key=lambda offer: offer[0])
            owner_retention = decisions.get(owner.id, _HOLD_DECISION).budget.retention
            resistance = employee.loyalty + owner.reputation + owner_retention // 1_000
            if best_score <= resistance:
                continue

            owner.employees.remove(employee)
            winner.employees.append(employee)
            transferred_employee_ids.setdefault(winner.id, set()).add(employee.id)
            _record_event(
                resolved,
                winner.id,
                f"Recruited {employee.name} from {owner.name}.",
            )
            _record_event(
                resolved,
                owner.id,
                f"Lost {employee.name} to {winner.name}.",
            )

        for company_id, decision in decisions.items():
            if decision.target_employee_ids and not transferred_employee_ids.get(company_id):
                _record_event(resolved, company_id, "Poaching: no employee offer was accepted.")

        return resolved

    def resolve_retention(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        resolved = state.model_copy(deep=True)
        for company in resolved.companies:
            decision = decisions.get(company.id)
            if decision is None:
                continue
            retention_levels = decision.budget.retention // RETENTION_COST_PER_LEVEL
            retention_points = retention_levels * RETENTION_POINTS_PER_LEVEL
            for employee in company.employees:
                employee.morale = min(100, employee.morale + retention_points)
                employee.loyalty = min(100, employee.loyalty + retention_points)
            if retention_points > 0:
                _record_event(
                    resolved,
                    company.id,
                    f"Retention: {len(company.employees)} employees gained "
                    f"+{retention_points} morale and loyalty.",
                )
        return resolved

    def resolve_clients(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        resolved = state.model_copy(deep=True)
        companies = {company.id: company for company in resolved.companies}
        won_clients: dict[str, list[str]] = {}
        revenue_by_company: dict[str, int] = {}
        expired_contracts: dict[str, list[str]] = {}

        for client in resolved.clients:
            if client.company_id is not None:
                continue
            contenders = [
                company
                for company in resolved.companies
                if client.id in decisions.get(company.id, _HOLD_DECISION).target_client_ids
            ]
            if not contenders:
                continue

            winner = max(
                contenders,
                key=lambda company: (
                    company.product_score + company.reputation + _sales_role_bonus(company)
                ),
            )
            client.company_id = winner.id
            client.contract_rounds_remaining = CLIENT_CONTRACT_ROUNDS
            if client.id not in winner.client_ids:
                winner.client_ids.append(client.id)
            won_clients.setdefault(winner.id, []).append(client.name)

        for client in resolved.clients:
            if client.company_id is None:
                continue
            company = companies[client.company_id]
            company.cash += client.revenue_per_round
            revenue_by_company[company.id] = (
                revenue_by_company.get(company.id, 0) + client.revenue_per_round
            )
            client.contract_rounds_remaining -= 1
            if client.contract_rounds_remaining == 0:
                company.client_ids.remove(client.id)
                client.company_id = None
                expired_contracts.setdefault(company.id, []).append(client.name)

        for company in resolved.companies:
            parts = []
            if company.id in won_clients:
                parts.append(f"won {len(won_clients[company.id])}")
            if company.id in revenue_by_company:
                parts.append(f"revenue +${revenue_by_company[company.id]:,}")
            if company.id in expired_contracts:
                parts.append(f"{len(expired_contracts[company.id])} contract(s) expired")
            if parts:
                _record_event(resolved, company.id, f"Clients: {'; '.join(parts)}.")

        return resolved

    def resolve_sabotage(
        self,
        state: GameState,
        decisions: Mapping[str, CompanyDecision],
    ) -> GameState:
        return state

    def process_payroll(self, state: GameState) -> GameState:
        resolved = state.model_copy(deep=True)
        for company in resolved.companies:
            gross_payroll = sum(employee.salary for employee in company.employees)
            discount_percent = min(
                MAX_PAYROLL_DISCOUNT_PERCENT,
                _role_power(company, EmployeeRole.OPERATIONS)
                // OPERATIONS_POWER_PER_PAYROLL_PERCENT,
            )
            payroll = gross_payroll * (100 - discount_percent) // 100
            if company.cash >= payroll:
                company.cash -= payroll
                discount_text = (
                    f" ({discount_percent}% operations discount)" if discount_percent else ""
                )
                _record_event(
                    resolved,
                    company.id,
                    f"Payroll paid: -${payroll:,}{discount_text}.",
                )
                continue

            company.cash = 0
            company.reputation = max(
                0,
                company.reputation - UNPAID_PAYROLL_REPUTATION_PENALTY,
            )
            for employee in company.employees:
                employee.morale = max(
                    0,
                    employee.morale - UNPAID_PAYROLL_MORALE_PENALTY,
                )
                employee.loyalty = max(
                    0,
                    employee.loyalty - UNPAID_PAYROLL_LOYALTY_PENALTY,
                )
            _record_event(
                resolved,
                company.id,
                f"Payroll missed: needed ${payroll:,}; morale -{UNPAID_PAYROLL_MORALE_PENALTY}, "
                f"loyalty -{UNPAID_PAYROLL_LOYALTY_PENALTY}, reputation "
                f"-{UNPAID_PAYROLL_REPUTATION_PENALTY}.",
            )
        return resolved

    def resolve_departures(self, state: GameState) -> GameState:
        resolved = state.model_copy(deep=True)
        for company in resolved.companies:
            remaining_employees = []
            for employee in company.employees:
                if employee.loyalty < DEPARTURE_LOYALTY_THRESHOLD:
                    _record_event(
                        resolved,
                        company.id,
                        f"{employee.name} left the company (loyalty: {employee.loyalty}).",
                    )
                    continue
                remaining_employees.append(employee)
            company.employees = remaining_employees
        return resolved


def _record_event(state: GameState, company_id: str, message: str) -> None:
    state.last_round_events.setdefault(company_id, []).append(message)


def _role_power(company: Company, role: EmployeeRole) -> int:
    return sum(
        employee.skill
        if employee.morale >= LOW_MORALE_THRESHOLD
        else employee.skill * LOW_MORALE_POWER_PERCENT // 100
        for employee in company.employees
        if employee.role == role
    )


def _product_role_bonus(company: Company, decision: CompanyDecision) -> int:
    if decision.budget.product == 0:
        return 0
    return (
        _role_power(company, EmployeeRole.ENGINEER) // ENGINEERING_POWER_PER_PRODUCT_POINT
        + _role_power(company, EmployeeRole.PRODUCT) // PRODUCT_POWER_PER_PRODUCT_POINT
    )


def _marketing_role_bonus(company: Company, decision: CompanyDecision) -> int:
    if decision.budget.marketing == 0:
        return 0
    return _role_power(company, EmployeeRole.MARKETING) // MARKETING_POWER_PER_REPUTATION_POINT


def _sales_role_bonus(company: Company) -> int:
    return _role_power(company, EmployeeRole.SALES) // SALES_POWER_PER_ACQUISITION_POINT


def _candidate_offer_score(
    company: Company,
    candidate: Employee,
    decision: CompanyDecision,
    budget_per_candidate: int,
) -> int:
    score = budget_per_candidate // 1_000 + company.reputation
    match candidate.personality:
        case EmployeePersonality.AMBITIOUS:
            score += company.product_score * 2
        case EmployeePersonality.VISIONARY:
            score += (decision.budget.product + decision.budget.training) // 5_000
        case EmployeePersonality.CREATIVE:
            score += company.reputation
        case EmployeePersonality.COMPETITIVE:
            score += budget_per_candidate // 1_000
        case EmployeePersonality.RELIABLE:
            score += min(company.cash, 500_000) // 10_000
    return score


def _recruitment_target_count(decision: CompanyDecision) -> int:
    return max(1, len(decision.target_candidate_ids) + len(decision.target_employee_ids))
