from llm_startup_arena.config import GameConfig
from llm_startup_arena.domain import Client, Company, Employee, EmployeeRole, GameState

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
