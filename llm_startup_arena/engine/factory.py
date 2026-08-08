from llm_startup_arena.config import GameConfig
from llm_startup_arena.domain import (
    Client,
    Company,
    Employee,
    EmployeePersonality,
    EmployeeRole,
    GameState,
)

COMPANY_IDENTITIES = (
    ("nova", "Nova Labs"),
    ("orbit", "Orbit AI"),
    ("pixel", "Pixel Forge"),
    ("apex", "Apex Systems"),
)

EMPLOYEE_ROLES = (
    EmployeeRole.ENGINEER,
    EmployeeRole.ENGINEER,
    EmployeeRole.PRODUCT,
    EmployeeRole.MARKETING,
    EmployeeRole.SALES,
)

EMPLOYEE_PERSONALITIES = (
    EmployeePersonality.AMBITIOUS,
    EmployeePersonality.RELIABLE,
    EmployeePersonality.VISIONARY,
    EmployeePersonality.CREATIVE,
    EmployeePersonality.COMPETITIVE,
)

EXTERNAL_CANDIDATES = (
    ("alex-chen", "Alex Chen", EmployeeRole.ENGINEER, EmployeePersonality.AMBITIOUS, 72, 8_000),
    ("maya-patel", "Maya Patel", EmployeeRole.PRODUCT, EmployeePersonality.VISIONARY, 68, 7_000),
    ("sofia-marin", "Sofia Marin", EmployeeRole.MARKETING, EmployeePersonality.CREATIVE, 65, 6_000),
    (
        "daniel-brooks",
        "Daniel Brooks",
        EmployeeRole.SALES,
        EmployeePersonality.COMPETITIVE,
        70,
        7_000,
    ),
    (
        "elena-ionescu",
        "Elena Ionescu",
        EmployeeRole.OPERATIONS,
        EmployeePersonality.RELIABLE,
        66,
        6_000,
    ),
)

CLIENT_SEGMENTS = ("startup", "small_business", "enterprise", "public_sector")


class GameFactory:
    """Build a reproducible starting state from the game configuration."""

    def __init__(self, config: GameConfig, models: tuple[str, ...]) -> None:
        if len(models) != config.company_count:
            raise ValueError("Each company must have exactly one model")
        if config.company_count != len(COMPANY_IDENTITIES):
            raise ValueError(f"This arena supports {len(COMPANY_IDENTITIES)} companies")

        self.config = config
        self.models = models

    def create(self) -> GameState:
        return GameState(
            round_number=0,
            companies=self._create_companies(),
            clients=self._create_clients(),
            available_candidates=self._create_candidates(),
        )

    def _create_companies(self) -> list[Company]:
        return [
            Company(
                id=company_id,
                name=name,
                model=model,
                cash=self.config.starting_cash,
                product_score=20,
                reputation=50,
                employees=self._create_employees(company_id),
            )
            for (company_id, name), model in zip(COMPANY_IDENTITIES, self.models, strict=True)
        ]

    def _create_employees(self, company_id: str) -> list[Employee]:
        return [
            Employee(
                id=f"{company_id}-employee-{index + 1}",
                name=f"{company_id.title()} Employee {index + 1}",
                role=EMPLOYEE_ROLES[index % len(EMPLOYEE_ROLES)],
                personality=EMPLOYEE_PERSONALITIES[index % len(EMPLOYEE_PERSONALITIES)],
                skill=50 + (index * 7) % 21,
                salary=4_000 + index * 500,
                morale=70 + (index * 3) % 11,
                loyalty=65 + (index * 5) % 16,
            )
            for index in range(self.config.starting_employees)
        ]

    def _create_clients(self) -> list[Client]:
        return [
            Client(
                id=f"client-{index + 1}",
                name=f"Client {index + 1}",
                segment=CLIENT_SEGMENTS[index % len(CLIENT_SEGMENTS)],
                revenue_per_round=8_000 + (index % 5) * 4_000,
                satisfaction=70,
            )
            for index in range(self.config.total_clients)
        ]

    @staticmethod
    def _create_candidates() -> list[Employee]:
        return [
            Employee(
                id=f"candidate-{candidate_id}",
                name=name,
                role=role,
                personality=personality,
                skill=skill,
                salary=salary,
                morale=70,
                loyalty=50,
            )
            for candidate_id, name, role, personality, skill, salary in EXTERNAL_CANDIDATES
        ]
