import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.llm.providers.gemini import GeminiProvider
from app.llm.providers.openai import OpenAIProvider
from app.llm.providers.ollama import OllamaProvider
from app.schemas.narrative import NarrativeResponse

# Sample valid JSON response that matches the NarrativeResponse Pydantic schema
VALID_JSON_RESPONSE = {
    "summary": "The market is showing strong momentum with institutional confluence.",
    "bias_score": 0.8,
    "key_levels": ["$450", "$460"],
    "risk_assessment": "Low risk of immediate reversal; monitor bandwidth."
}
VALID_JSON_STRING = json.dumps(VALID_JSON_RESPONSE)


@pytest.mark.asyncio
@patch("app.llm.providers.gemini.settings")
@patch("app.llm.providers.gemini.genai.GenerativeModel")
async def test_gemini_provider(mock_model_class, mock_settings):
    # 1. Setup mock config
    mock_settings.GEMINI_API_KEY = "test_gemini_key"
    
    # 2. Setup mock response
    mock_model_instance = AsyncMock()
    mock_model_class.return_value = mock_model_instance
    
    mock_response = MagicMock()
    # We simulate Gemini wrapping the output in markdown codeblocks (the provider strips this)
    mock_response.text = f"```json\n{VALID_JSON_STRING}\n```"
    mock_model_instance.generate_content_async.return_value = mock_response

    # 3. Execute
    provider = GeminiProvider()
    result = await provider.generate_narrative({"trend": "bullish"})

    # 4. Assert
    assert isinstance(result, NarrativeResponse)
    narrative_val = getattr(result, "narrative", result)
    narrative_obj = json.loads(narrative_val) if isinstance(narrative_val, str) else narrative_val
    summary = narrative_obj.get("summary") if isinstance(narrative_obj, dict) else getattr(narrative_obj, "summary", None)
    bias_score = narrative_obj.get("bias_score") if isinstance(narrative_obj, dict) else getattr(narrative_obj, "bias_score", None)
    assert summary == VALID_JSON_RESPONSE["summary"]
    assert bias_score == VALID_JSON_RESPONSE["bias_score"]
    mock_model_instance.generate_content_async.assert_called_once()


@pytest.mark.asyncio
@patch("app.llm.providers.openai.settings")
@patch("app.llm.providers.openai.AsyncOpenAI")
async def test_openai_provider(mock_async_openai_class, mock_settings):
    # 1. Setup mock config
    mock_settings.OPENAI_API_KEY = "test_openai_key"
    
    # 2. Setup mock response
    mock_client_instance = AsyncMock()
    mock_async_openai_class.return_value = mock_client_instance
    
    mock_message = MagicMock()
    mock_message.content = VALID_JSON_STRING
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client_instance.chat.completions.create.return_value = mock_response

    # 3. Execute
    provider = OpenAIProvider()
    result = await provider.generate_narrative({"trend": "bullish"})

    # 4. Assert
    assert isinstance(result, NarrativeResponse)
    narrative_val = getattr(result, "narrative", result)
    narrative_obj = json.loads(narrative_val) if isinstance(narrative_val, str) else narrative_val
    summary = narrative_obj.get("summary") if isinstance(narrative_obj, dict) else getattr(narrative_obj, "summary", None)
    key_levels = narrative_obj.get("key_levels") if isinstance(narrative_obj, dict) else getattr(narrative_obj, "key_levels", None)
    assert summary == VALID_JSON_RESPONSE["summary"]
    assert key_levels == VALID_JSON_RESPONSE["key_levels"]
    mock_client_instance.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
@patch("app.llm.providers.ollama.settings")
@patch("app.llm.providers.ollama.httpx.AsyncClient")
async def test_ollama_provider(mock_async_client_class, mock_settings):
    # 1. Setup mock config
    mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"
    mock_settings.OLLAMA_MODEL = "llama3"
    
    # 2. Setup mock response for the async context manager (`async with httpx.AsyncClient()`)
    mock_client_instance = AsyncMock()
    mock_async_client_class.return_value.__aenter__.return_value = mock_client_instance
    
    mock_response = MagicMock()
    # Ollama returns the generated text under the "response" key in its JSON payload
    mock_response.json.return_value = {"response": VALID_JSON_STRING}
    mock_client_instance.post.return_value = mock_response

    # 3. Execute
    provider = OllamaProvider()
    result = await provider.generate_narrative({"trend": "bullish"})

    # 4. Assert
    assert isinstance(result, NarrativeResponse)
    narrative_val = getattr(result, "narrative", result)
    narrative_obj = json.loads(narrative_val) if isinstance(narrative_val, str) else narrative_val
    summary = narrative_obj.get("summary") if isinstance(narrative_obj, dict) else getattr(narrative_obj, "summary", None)
    assert summary == VALID_JSON_RESPONSE["summary"]
    mock_client_instance.post.assert_called_once()