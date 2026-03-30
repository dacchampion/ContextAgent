from enum import Enum

from app.core.config import settings
from app.llm.enums import NarratorType
from app.llm.providers.base import BaseLLMProvider


class LLMProviderType(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    OLLAMA = "ollama"


class LLMFactory:
    """Factory for creating LLM provider instances."""

    @staticmethod
    def create_narrator(_narrator_type: NarratorType) -> BaseLLMProvider:
        """Creates a provider instance based on configured provider type."""
        provider_type = settings.LLM_PROVIDER_TYPE.strip().lower()

        if provider_type == LLMProviderType.GEMINI.value:
            from app.llm.providers.gemini import GeminiProvider

            return GeminiProvider()
        if provider_type == LLMProviderType.OPENAI.value:
            from app.llm.providers.openai import OpenAIProvider

            return OpenAIProvider()
        if provider_type == LLMProviderType.OLLAMA.value:
            from app.llm.providers.ollama import OllamaProvider

            return OllamaProvider()

        raise ValueError(f"Unsupported LLM provider type: {settings.LLM_PROVIDER_TYPE}")
