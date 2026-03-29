# backend/app/llm/providers/openai.py
import os
import json
from openai import AsyncOpenAI
from typing import Dict, Any

from app.llm.providers.base import BaseLLMProvider
from app.schemas.narrative import NarrativeResponse
from app.llm.prompts import SYSTEM_PROMPT
from app.core.config import settings

class OpenAIProvider(BaseLLMProvider):
    """
    LLM provider for OpenAI's models (e.g., GPT-4o).
    """

    def __init__(self):
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = settings.OPENAI_MODEL

    async def generate_narrative(self, context_data: Dict[str, Any]) -> NarrativeResponse:
        """
        Generates a market narrative using the OpenAI API.
        """
        # Note: This is a skeleton. Error handling and JSON parsing are simplified.
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"""Here is the market data:

{context_data}"""}
                ],
                # response_format={"type": "json_object"}, # For newer models
            )
            
            response_content = response.choices[0].message.content
            narrative_dict = json.loads(response_content)
            symbol = context_data.get("symbol", "UNKNOWN")
            timeframe = context_data.get("timeframe", "UNKNOWN")
            return NarrativeResponse(symbol=symbol, timeframe=timeframe, narrative=json.dumps(narrative_dict))
        except Exception as e:
            # Add robust error handling here
            print(f"Error generating narrative with OpenAI: {e}")
            raise
