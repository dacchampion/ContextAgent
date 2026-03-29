# backend/app/llm/providers/gemini.py
import os
import json
import google.generativeai as genai
from typing import Dict, Any

from app.llm.providers.base import BaseLLMProvider
from app.schemas.narrative import NarrativeResponse
from app.llm.prompts import SYSTEM_PROMPT
from app.core.config import settings

class GeminiProvider(BaseLLMProvider):
    """
    LLM provider for Google's Gemini models.
    """

    def __init__(self):
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def generate_narrative(self, context_data: Dict[str, Any]) -> NarrativeResponse:
        """
        Generates a market narrative using the Gemini API.
        """
        # Note: This is a skeleton. Error handling and JSON parsing are simplified.
        try:
            prompt = f"""{SYSTEM_PROMPT}

Here is the market data:

{context_data}"""
            response = await self.model.generate_content_async(prompt)
            
            response_text = response.text.strip()
            # Strip potential markdown formatting
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            elif response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            narrative_dict = json.loads(response_text.strip())
            symbol = context_data.get("symbol", "UNKNOWN")
            timeframe = context_data.get("timeframe", "UNKNOWN")
            return NarrativeResponse(symbol=symbol, timeframe=timeframe, narrative=json.dumps(narrative_dict))
        except Exception as e:
            # Add robust error handling here
            print(f"Error generating narrative with Gemini: {e}")
            raise
