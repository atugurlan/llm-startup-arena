from pydantic import BaseModel, Field

from .provider import CompanyDecision


class RoundDecisionRecord(BaseModel):
    """Decisions and model failures collected for one game round."""

    round_number: int = Field(ge=1)
    decisions: dict[str, CompanyDecision] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)

    def model_post_init(self, __context: object, /) -> None:
        overlap = self.decisions.keys() & self.errors.keys()
        if overlap:
            companies = ", ".join(sorted(overlap))
            raise ValueError(f"Companies cannot have both a decision and an error: {companies}")
