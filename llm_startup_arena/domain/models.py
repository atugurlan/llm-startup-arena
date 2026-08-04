from enum import StrEnum

from pydantic import BaseModel, Field


class EmployeeRole(StrEnum):
    ENGINEER = "engineer"
    PRODUCT = "product"
    MARKETING = "marketing"
    SALES = "sales"
    OPERATIONS = "operations"


class Employee(BaseModel):
    id: str
    name: str
    role: EmployeeRole
    skill: int = Field(ge=0, le=100)
    salary: int = Field(ge=0)
    morale: int = Field(default=70, ge=0, le=100)
    loyalty: int = Field(default=70, ge=0, le=100)
    experience: int = Field(default=0, ge=0)


class Client(BaseModel):
    id: str
    name: str
    segment: str
    revenue_per_round: int = Field(ge=0)
    satisfaction: int = Field(default=70, ge=0, le=100)
    contract_rounds_remaining: int = Field(default=0, ge=0)
    company_id: str | None = None


class MarketEvent(BaseModel):
    id: str
    name: str
    description: str
    modifiers: dict[str, float] = Field(default_factory=dict)


class Company(BaseModel):
    id: str
    name: str
    model: str
    cash: int = Field(ge=0)
    product_score: int = Field(default=0, ge=0, le=100)
    reputation: int = Field(default=50, ge=0, le=100)
    employees: list[Employee] = Field(default_factory=list)
    client_ids: list[str] = Field(default_factory=list)


class GameState(BaseModel):
    round_number: int = Field(default=0, ge=0)
    companies: list[Company]
    clients: list[Client]
    market_event: MarketEvent | None = None
