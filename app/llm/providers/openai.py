# backend/app/llm/providers/openai.py
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
        # Note: Keep a tolerant parser so model output formatting does not 500 the endpoint.
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"""Here is the market data:

{context_data}"""}
                ],
                response_format={"type": "json_object"},
            )

            response_content = (response.choices[0].message.content or "").strip()
            if not response_content:
                raise ValueError("OpenAI returned empty content for narrative generation.")

            # First pass: expected strict JSON object.
            try:
                narrative_dict = json.loads(response_content)
            except json.JSONDecodeError:
                # Second pass: tolerate markdown code fences.
                cleaned = response_content
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                narrative_dict = json.loads(cleaned)

            symbol = context_data.get("symbol", "UNKNOWN")
            timeframe = context_data.get("timeframe", "UNKNOWN")
            return NarrativeResponse(symbol=symbol, timeframe=timeframe, narrative=json.dumps(narrative_dict))
        except Exception as e:
            print(f"Error generating narrative with OpenAI: {e}")
            raise
