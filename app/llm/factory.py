# backend/app/llm/factory.py
from enum import Enum
from app.core.config import settings
from app.llm.providers.base import BaseLLMProvider

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
    def create_llm_provider() -> BaseLLMProvider:
        """
        Creates an LLM provider based on the LLM_PROVIDER_TYPE environment variable.
        """
        provider_type_str = settings.LLM_PROVIDER_TYPE.lower()

        if provider_type_str == LLMProviderType.GEMINI:
            from .providers.gemini import GeminiProvider
            return GeminiProvider()
        elif provider_type_str == LLMProviderType.OPENAI:
            from .providers.openai import OpenAIProvider
            return OpenAIProvider()
        elif provider_type_str == LLMProviderType.OLLAMA:
            from .providers.ollama import OllamaProvider
            return OllamaProvider()
        # Add other providers here
        else:
            raise ValueError(f"Unsupported LLM provider type: {provider_type_str}")

# A global instance for easy access
llm_provider = LLMFactory.create_llm_provider()
