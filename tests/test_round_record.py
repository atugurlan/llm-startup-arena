import pytest
from pydantic import ValidationError

from llm_startup_arena.llm import (
    BudgetAllocation,
    CompanyDecision,
    RoundDecisionRecord,
)


def test_record_separates_decisions_from_errors() -> None:
    decision = CompanyDecision(strategy="grow", budget=BudgetAllocation(product=10))

    record = RoundDecisionRecord(
        round_number=1,
        decisions={"nova": decision},
        errors={"orbit": "model timed out"},
    )

    assert record.decisions["nova"] == decision
    assert record.errors["orbit"] == "model timed out"


def test_record_rejects_two_outcomes_for_same_company() -> None:
    decision = CompanyDecision(strategy="grow", budget=BudgetAllocation())

    with pytest.raises(ValidationError, match="both a decision and an error"):
        RoundDecisionRecord(
            round_number=1,
            decisions={"nova": decision},
            errors={"nova": "invalid response"},
        )
