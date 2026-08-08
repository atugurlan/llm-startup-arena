from pydantic import BaseModel, Field

from llm_startup_arena.domain import Company, GameState

PRODUCT_POINT_VALUE = 5_000
REPUTATION_POINT_VALUE = 5_000
EMPLOYEE_SKILL_VALUE = 1_000
EMPLOYEE_EXPERIENCE_VALUE = 500
EMPLOYEE_MORALE_VALUE = 250
EMPLOYEE_LOYALTY_VALUE = 250


class CompanyScore(BaseModel):
    """Final valuation and rank for one company."""

    position: int = Field(ge=1)
    company_id: str
    company_name: str
    model: str
    cash_value: int = Field(ge=0)
    product_value: int = Field(ge=0)
    reputation_value: int = Field(ge=0)
    client_value: int = Field(ge=0)
    employee_value: int = Field(ge=0)
    total_value: int = Field(ge=0)


class GameResult(BaseModel):
    """Ordered final standings for a completed game."""

    rankings: list[CompanyScore]

    @property
    def winner(self) -> CompanyScore:
        if not self.rankings:
            raise ValueError("Cannot select a winner without ranked companies")
        return self.rankings[0]


class CompanyRanker:
    """Calculate deterministic company valuations and final standings."""

    def rank(self, state: GameState) -> GameResult:
        valuations = [self._value_company(company, state) for company in state.companies]
        ordered = sorted(
            valuations,
            key=lambda score: (
                -score.total_value,
                -score.cash_value,
                -score.client_value,
                -score.product_value,
                -score.reputation_value,
                -score.employee_value,
                score.company_id,
            ),
        )
        rankings = [
            score.model_copy(update={"position": position})
            for position, score in enumerate(ordered, start=1)
        ]
        return GameResult(rankings=rankings)

    @staticmethod
    def _value_company(company: Company, state: GameState) -> CompanyScore:
        cash_value = company.cash
        product_value = company.product_score * PRODUCT_POINT_VALUE
        reputation_value = company.reputation * REPUTATION_POINT_VALUE
        client_value = sum(
            client.revenue_per_round * client.contract_rounds_remaining
            for client in state.clients
            if client.company_id == company.id
        )
        employee_value = sum(
            employee.skill * EMPLOYEE_SKILL_VALUE
            + employee.experience * EMPLOYEE_EXPERIENCE_VALUE
            + employee.morale * EMPLOYEE_MORALE_VALUE
            + employee.loyalty * EMPLOYEE_LOYALTY_VALUE
            for employee in company.employees
        )
        total_value = cash_value + product_value + reputation_value + client_value + employee_value
        return CompanyScore(
            position=1,
            company_id=company.id,
            company_name=company.name,
            model=company.model,
            cash_value=cash_value,
            product_value=product_value,
            reputation_value=reputation_value,
            client_value=client_value,
            employee_value=employee_value,
            total_value=total_value,
        )
