from sqlalchemy.orm import Session
from app.services.context_builder import build_context_json
from app.llm.factory import LLMFactory, NarratorType
from app.schemas.narrative import NarrativeResponse

# Placeholder for GEX context builder
def build_gex_context_json(db_session: Session, symbol: str):
    # In the future, this would fetch GEX data, for now, it's a placeholder
    return {"symbol": symbol, "gex_data": "some_gex_data"}

class NarratorService:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def generate_narrative(self, symbol: str, timeframe: str, narrator_type: NarratorType) -> NarrativeResponse:
        # 1. Fetch the context based on the narrator type
        if narrator_type == NarratorType.TECHNICAL:
            context = build_context_json(self.db_session, symbol, [timeframe])
        elif narrator_type == NarratorType.GEX:
            context = build_gex_context_json(self.db_session, symbol)
        else:
            raise ValueError(f"Unsupported narrator type: {narrator_type}")

        # 2. Use the LLMFactory to get the narrator
        narrator = LLMFactory.create_narrator(narrator_type)
        narrative_text = narrator.narrate(context)

        # 3. Return the narrative in the Pydantic model
        return NarrativeResponse(
            symbol=symbol,
            timeframe=timeframe,
            narrative=narrative_text,
        )
