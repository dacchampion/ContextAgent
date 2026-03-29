# backend/app/llm/providers/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

from app.schemas.narrative import NarrativeResponse

class BaseLLMProvider(ABC):
    """
    Abstract base class for all LLM providers.
    """

    @abstractmethod
    async def generate_narrative(self, symbol: str, timeframe: str, context_data: Dict[str, Any]) -> NarrativeResponse:
        """
        Generates a market narrative based on the provided context data.

        Args:
            symbol: The symbol to generate the narrative for.
            timeframe: The timeframe to generate the narrative for.
            context_data: A dictionary containing the technical market data.

        Returns:
            A NarrativeResponse object with the generated narrative.
        """
        pass
