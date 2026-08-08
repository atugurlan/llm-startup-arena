from pydantic import BaseModel, Field

from .models import GameState


class CompanySnapshot(BaseModel):
    """Chart-ready company metrics captured at the end of a round."""

    company_id: str
    company_name: str
    model: str
    cash: int = Field(ge=0)
    product_score: int = Field(ge=0, le=100)
    reputation: int = Field(ge=0, le=100)
    employee_count: int = Field(ge=0)
    client_count: int = Field(ge=0)


class RoundSnapshot(BaseModel):
    """Metrics for every company at one point in the game timeline."""

    round_number: int = Field(ge=0)
    companies: list[CompanySnapshot]

    @classmethod
    def from_state(cls, state: GameState) -> "RoundSnapshot":
        return cls(
            round_number=state.round_number,
            companies=[
                CompanySnapshot(
                    company_id=company.id,
                    company_name=company.name,
                    model=company.model,
                    cash=company.cash,
                    product_score=company.product_score,
                    reputation=company.reputation,
                    employee_count=len(company.employees),
                    client_count=len(company.client_ids),
                )
                for company in state.companies
            ],
        )
