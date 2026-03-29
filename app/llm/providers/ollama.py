# backend/app/llm/providers/ollama.py
import httpx
import json
from typing import Dict, Any

from app.llm.providers.base import BaseLLMProvider
from app.schemas.narrative import NarrativeResponse
from app.llm.prompts import SYSTEM_PROMPT
from app.core.config import settings

class OllamaProvider(BaseLLMProvider):
    """
    LLM provider for local/open-source models via Ollama.
    """

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        if not self.base_url:
            raise ValueError("OLLAMA_BASE_URL environment variable not set.")
        if not self.model:
            raise ValueError("OLLAMA_MODEL environment variable not set.")

    async def generate_narrative(self, context_data: Dict[str, Any]) -> NarrativeResponse:
        """
        Generates a market narrative using the Ollama API.
        """
        # Note: This is a skeleton. Error handling and JSON parsing are simplified.
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "system": SYSTEM_PROMPT,
                        "prompt": f"""Here is the market data:

{context_data}""",
                        "format": "json", # Assuming the model supports JSON output
                        "stream": False,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()

            response_data = response.json()
            narrative_dict = json.loads(response_data.get("response", "{}"))
            symbol = context_data.get("symbol", "UNKNOWN")
            timeframe = context_data.get("timeframe", "UNKNOWN")
            return NarrativeResponse(symbol=symbol, timeframe=timeframe, narrative=json.dumps(narrative_dict))
        except httpx.RequestError as e:
            # Handle connection errors, timeouts, etc.
            print(f"Error generating narrative with Ollama: {e}")
            raise
        except Exception as e:
            # Handle other potential errors
            print(f"An unexpected error occurred: {e}")
            raise
