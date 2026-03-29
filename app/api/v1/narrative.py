from fastapi import APIRouter, Depends
from app.schemas.narrative import NarrativeRequest, NarrativeResponse
from app.services.narrator import NarratorService
from app.api.deps import get_narrator_service

router = APIRouter()

@router.post("/narrative", response_model=NarrativeResponse)
def get_narrative(
    request: NarrativeRequest,
    narrator_service: NarratorService = Depends(get_narrator_service)
):
    """
    Generate an actionable market narrative based on the latest technical or GEX context.
    """
    return narrator_service.generate_narrative(
        symbol=request.symbol,
        timeframe=request.timeframe,
        narrator_type=request.narrator_type
    )
