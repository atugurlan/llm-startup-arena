from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field

from llm_startup_arena.domain import GameState


class SabotageAction(StrEnum):
    """Sabotage strategies supported by the game contract."""

    PRODUCT_DISRUPTION = "product_disruption"
    REPUTATION_ATTACK = "reputation_attack"
    CLIENT_INTERFERENCE = "client_interference"
    TALENT_DISRUPTION = "talent_disruption"


class BudgetAllocation(BaseModel):
    """Money assigned by a company to each strategic category."""

    product: int = Field(default=0, ge=0)
    marketing: int = Field(default=0, ge=0)
    training: int = Field(default=0, ge=0)
    recruitment: int = Field(default=0, ge=0)
    retention: int = Field(default=0, ge=0)
    sabotage: int = Field(default=0, ge=0)

    @property
    def total(self) -> int:
        return sum(
            (
                self.product,
                self.marketing,
                self.training,
                self.recruitment,
                self.retention,
                self.sabotage,
            )
        )


class CompanyDecision(BaseModel):
    """Validated action selected by one LLM for a single round."""

    strategy: str = Field(min_length=1)
    budget: BudgetAllocation
    target_client_ids: list[str] = Field(
        default_factory=list,
        max_length=2,
        description="Unique existing client IDs targeted this round, or an empty list",
    )
    target_employee_ids: list[str] = Field(
        default_factory=list,
        max_length=2,
        description="Unique employee IDs belonging only to competing companies, or an empty list",
    )
    target_candidate_ids: list[str] = Field(
        default_factory=list,
        max_length=2,
        description="Unique available external candidate IDs targeted this round, or an empty list",
    )
    sabotage_action: SabotageAction | None = Field(
        default=None,
        description="Required when sabotage budget is positive; otherwise null",
    )
    target_company_id: str | None = Field(
        default=None,
        description="Competing company targeted by sabotage, or null without sabotage",
    )


class LLMProvider(Protocol):
    """Interface implemented by any model runtime used by the arena."""

    def generate_decision(
        self,
        *,
        model: str,
        company_id: str,
        state: GameState,
    ) -> CompanyDecision: ...
