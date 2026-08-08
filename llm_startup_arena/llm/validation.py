from llm_startup_arena.domain import Company, GameState

from .provider import CompanyDecision


class DecisionValidationError(ValueError):
    """Raised when a company decision violates one or more game rules."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(errors))


class DecisionNormalizer:
    """Repair harmless LLM target and sabotage inconsistencies before validation."""

    def normalize(
        self,
        *,
        company_id: str,
        decision: CompanyDecision,
        state: GameState,
    ) -> CompanyDecision:
        company = DecisionValidator._find_company(company_id, state)
        normalized = decision.model_copy(deep=True)
        available_clients = {client.id for client in state.clients if client.company_id is None}
        recruitable_employees = {
            employee.id
            for owner in state.companies
            if owner.id != company.id
            for employee in owner.employees
        }

        normalized.target_client_ids = _unique_valid_ids(
            normalized.target_client_ids,
            available_clients,
        )
        normalized.target_employee_ids = _unique_valid_ids(
            normalized.target_employee_ids,
            recruitable_employees,
        )
        normalized.target_candidate_ids = _unique_valid_ids(
            normalized.target_candidate_ids,
            {candidate.id for candidate in state.available_candidates},
        )

        if normalized.budget.recruitment == 0:
            normalized.target_candidate_ids = []
            normalized.target_employee_ids = []

        normalized.budget.sabotage = 0
        normalized.sabotage_action = None

        return normalized


class DecisionValidator:
    """Validate an LLM decision against the current game state."""

    def validate(
        self,
        *,
        company_id: str,
        decision: CompanyDecision,
        state: GameState,
    ) -> CompanyDecision:
        company = self._find_company(company_id, state)
        errors = [
            *self._validate_budget(company, decision),
            *self._validate_client_targets(decision, state),
            *self._validate_employee_targets(company, decision, state),
            *self._validate_candidate_targets(decision, state),
            *self._validate_sabotage(decision),
        ]
        if errors:
            raise DecisionValidationError(errors)
        return decision

    @staticmethod
    def _find_company(company_id: str, state: GameState) -> Company:
        company = next(
            (candidate for candidate in state.companies if candidate.id == company_id),
            None,
        )
        if company is None:
            raise DecisionValidationError([f"Unknown company: {company_id}"])
        return company

    @staticmethod
    def _validate_budget(
        company: Company,
        decision: CompanyDecision,
    ) -> list[str]:
        if decision.budget.total <= company.cash:
            return []
        return [f"Budget {decision.budget.total} exceeds available cash {company.cash}"]

    @staticmethod
    def _validate_client_targets(
        decision: CompanyDecision,
        state: GameState,
    ) -> list[str]:
        errors = _duplicate_errors(decision.target_client_ids, "client")
        available_clients = {client.id for client in state.clients if client.company_id is None}
        invalid_clients = set(decision.target_client_ids) - available_clients
        if invalid_clients:
            errors.append(f"Unknown or unavailable clients: {', '.join(sorted(invalid_clients))}")
        return errors

    @staticmethod
    def _validate_employee_targets(
        company: Company,
        decision: CompanyDecision,
        state: GameState,
    ) -> list[str]:
        errors = _duplicate_errors(decision.target_employee_ids, "employee")
        employee_owners = {
            employee.id: owner.id for owner in state.companies for employee in owner.employees
        }
        unknown_employees = set(decision.target_employee_ids) - employee_owners.keys()
        if unknown_employees:
            errors.append(f"Unknown employees: {', '.join(sorted(unknown_employees))}")

        own_employees = {
            employee_id
            for employee_id in decision.target_employee_ids
            if employee_owners.get(employee_id) == company.id
        }
        if own_employees:
            errors.append(f"Cannot recruit own employees: {', '.join(sorted(own_employees))}")
        return errors

    @staticmethod
    def _validate_sabotage(decision: CompanyDecision) -> list[str]:
        has_budget = decision.budget.sabotage > 0
        has_action = bool(decision.sabotage_action and decision.sabotage_action.strip())
        if has_budget == has_action:
            return []
        if has_budget:
            return ["Sabotage budget requires a sabotage action"]
        return ["Sabotage action requires a sabotage budget"]

    @staticmethod
    def _validate_candidate_targets(
        decision: CompanyDecision,
        state: GameState,
    ) -> list[str]:
        errors = _duplicate_errors(decision.target_candidate_ids, "candidate")
        available_candidates = {candidate.id for candidate in state.available_candidates}
        invalid_candidates = set(decision.target_candidate_ids) - available_candidates
        if invalid_candidates:
            errors.append(
                f"Unknown or unavailable candidates: {', '.join(sorted(invalid_candidates))}"
            )
        return errors


def _duplicate_errors(target_ids: list[str], target_type: str) -> list[str]:
    if len(target_ids) == len(set(target_ids)):
        return []
    return [f"Duplicate {target_type} targets are not allowed"]


def _unique_valid_ids(target_ids: list[str], valid_ids: set[str]) -> list[str]:
    return list(dict.fromkeys(target_id for target_id in target_ids if target_id in valid_ids))
