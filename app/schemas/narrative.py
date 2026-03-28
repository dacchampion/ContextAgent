from pydantic import BaseModel, Field
from typing import List

class NarrativeResponse(BaseModel):
    """
    Represents the structured narrative output from an LLM provider.
    """
    summary: str = Field(..., description="A high-level summary of the market narrative.")
    bias_score: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="A score from -1.0 (very bearish) to 1.0 (very bullish).",
    )
    key_levels: List[str] = Field(
        default_factory=list, description="Key support and resistance levels identified."
    )
    risk_assessment: str = Field(
        ..., description="An assessment of the current risks and market conditions."
    )
