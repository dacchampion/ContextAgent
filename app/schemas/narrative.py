from pydantic import BaseModel, Field
from app.llm.enums import NarratorType

class NarrativeRequest(BaseModel):
    symbol: str = Field(..., description="The symbol to generate the narrative for.")
    timeframe: str = Field(..., description="The timeframe to generate the narrative for.")
    narrator_type: NarratorType = Field(..., description="The type of narrator to use.")

class NarrativeResponse(BaseModel):
    """
    Represents the structured narrative output from an LLM provider.
    """
    symbol: str = Field(..., description="The symbol the narrative is for.")
    timeframe: str = Field(..., description="The timeframe the narrative is for.")
    narrative: str = Field(..., description="The generated narrative.")
