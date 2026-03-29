# backend/app/llm/factory.py
from enum import Enum
from app.core.config import settings
from app.llm.providers.base import BaseLLMProvider
from app.llm.enums import NarratorType

class LLMProviderType(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    OLLAMA = "ollama"
    # Add vLLM here when implemented

class LLMFactory:
    """
    Factory for creating LLM provider instances.
    """

    @staticmethod
    def create_narrator(narrator_type: NarratorType) -> BaseLLMProvider:
        """
        Creates a narrator provider based on the narrator_type.
        """
        if narrator_type == NarratorType.TECHNICAL:
            from app.llm.narrators.technical import TechnicalNarrator
            return TechnicalNarrator()
        elif narrator_type == NarratorType.GEX:
            from app.llm.narrators.gex import GEXNarrator
            return GEXNarrator()
        else:
            raise ValueError(f"Unsupported narrator type: {narrator_type}")
