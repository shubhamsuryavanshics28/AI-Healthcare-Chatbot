"""
Automated Test Suite for Phase 2: Gemini LLM Integration & Provider Abstraction
Verifies:
1. Gemini client initialization.
2. Successful response generation.
3. Successful streaming response.
4. Missing API key handling.
5. Invalid API key handling.
6. HTTP 429 rate limit handling.
7. HTTP 503 temporary unavailability handling.
8. Timeout handling.
9. Empty response handling.
10. Provider fallback routing.
11. Emergency detection when Gemini is unavailable.
12. RAG context integration with Gemini.
13. Normal chat endpoint integration with Gemini.
14. Streaming chat endpoint integration with Gemini.
15. Strict safety against leaking API keys or raw exceptions.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status

from google.genai import errors
from backend.config import settings
from backend.services.gemini_service import (
    gemini_service,
    get_gemini_client,
    reset_gemini_client,
    GeminiResponse
)
from backend.services.llm_service import llm_service, LLMResult
from backend.services.ai_service import generate_chat_response, stream_chat_response


# ==============================================================================
# 1. Gemini Client Initialization
# ==============================================================================

def test_gemini_client_initialization():
    """Verify Gemini client initializes with a configured key and returns None without one."""
    reset_gemini_client()
    with patch.object(settings, "GEMINI_API_KEY", "test-mock-gemini-key"):
        client = get_gemini_client()
        assert client is not None

    reset_gemini_client()
    with patch.object(settings, "GEMINI_API_KEY", ""):
        client = get_gemini_client()
        assert client is None
    reset_gemini_client()


# ==============================================================================
# 2. Successful Non-Streaming Response Generation
# ==============================================================================

@pytest.mark.asyncio
async def test_successful_response_generation():
    """Verify Gemini successfully generates a healthcare response with token counts."""
    mock_response = MagicMock()
    mock_response.text = "Rest in a quiet room, drink cool water, and apply a cool compress to your forehead."
    mock_response.usage_metadata.total_token_count = 42

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("backend.services.gemini_service.get_gemini_client", return_value=mock_client):
        resp = await gemini_service.generate_chat(
            system_instruction="You are ArogyaAI",
            conversation_history=[],
            user_message="I have a mild tension headache."
        )
        assert resp.is_success is True
        assert "Rest in a quiet room" in resp.content
        assert resp.tokens_used == 42
        assert resp.error is None


# ==============================================================================
# 3. Successful Streaming Response Generation
# ==============================================================================

@pytest.mark.asyncio
async def test_successful_streaming_response():
    """Verify Gemini streams progressive token chunks."""
    async def mock_chunk_generator():
        for token in ["Drink ", "adequate ", "water ", "and ", "rest."]:
            chunk = MagicMock()
            chunk.text = token
            yield chunk

    mock_client = MagicMock()
    mock_client.aio.models.generate_content_stream = AsyncMock(return_value=mock_chunk_generator())

    with patch("backend.services.gemini_service.get_gemini_client", return_value=mock_client):
        collected_tokens = []
        async for token in gemini_service.stream_chat(
            system_instruction="You are ArogyaAI",
            conversation_history=[],
            user_message="I have mild fever."
        ):
            collected_tokens.append(token)

        assert "".join(collected_tokens) == "Drink adequate water and rest."


# ==============================================================================
# 4. Missing API Key Handling
# ==============================================================================

@pytest.mark.asyncio
async def test_missing_api_key_handling():
    """Verify missing API key returns a structured error without throwing unhandled exceptions."""
    with patch("backend.services.gemini_service.get_gemini_client", return_value=None):
        resp = await gemini_service.generate_chat(
            system_instruction="You are ArogyaAI",
            conversation_history=[],
            user_message="Hello"
        )
        assert resp.is_success is False
        assert resp.error_code == 401
        assert "not configured" in resp.error.lower()


# ==============================================================================
# 5. Invalid API Key Handling (HTTP 403 / 401)
# ==============================================================================

@pytest.mark.asyncio
async def test_invalid_api_key_handling():
    """Verify invalid API key (HTTP 403) terminates immediately without infinite retries."""
    mock_err = errors.APIError(code=403, response_json={"error": "API_KEY_INVALID"})
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=mock_err)

    with patch("backend.services.gemini_service.get_gemini_client", return_value=mock_client):
        resp = await gemini_service.generate_chat(
            system_instruction="You are ArogyaAI",
            conversation_history=[],
            user_message="Hello"
        )
        assert resp.is_success is False
        assert resp.error_code == 403
        # Ensure it was called only once (no retries for auth errors)
        assert mock_client.aio.models.generate_content.call_count == 1


# ==============================================================================
# 6. HTTP 429 Rate Limit Handling
# ==============================================================================

@pytest.mark.asyncio
async def test_http_429_rate_limit_handling():
    """Verify HTTP 429 rate limit triggers bounded retries and clean error return upon exhaustion."""
    mock_err = errors.APIError(code=429, response_json={"error": "RESOURCE_EXHAUSTED"})
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=mock_err)

    with patch("backend.services.gemini_service.get_gemini_client", return_value=mock_client), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        resp = await gemini_service.generate_chat(
            system_instruction="You are ArogyaAI",
            conversation_history=[],
            user_message="Hello"
        )
        assert resp.is_success is False
        assert resp.error_code == 429
        # Max retries = 2, so total calls = 1 initial + 2 retries = 3
        assert mock_client.aio.models.generate_content.call_count == 3


# ==============================================================================
# 7. HTTP 503 Temporary Unavailability Handling
# ==============================================================================

@pytest.mark.asyncio
async def test_http_503_service_unavailable_handling():
    """Verify HTTP 503 service unavailable triggers bounded retries with graceful error."""
    mock_err = errors.APIError(code=503, response_json={"error": "UNAVAILABLE"})
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=mock_err)

    with patch("backend.services.gemini_service.get_gemini_client", return_value=mock_client), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        resp = await gemini_service.generate_chat(
            system_instruction="You are ArogyaAI",
            conversation_history=[],
            user_message="Hello"
        )
        assert resp.is_success is False
        assert resp.error_code == 503
        assert mock_client.aio.models.generate_content.call_count == 3


# ==============================================================================
# 8. Timeout Handling
# ==============================================================================

@pytest.mark.asyncio
async def test_timeout_handling():
    """Verify timeout triggers clean error return without unhandled exception."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=asyncio.TimeoutError())

    with patch("backend.services.gemini_service.get_gemini_client", return_value=mock_client):
        resp = await gemini_service.generate_chat(
            system_instruction="You are ArogyaAI",
            conversation_history=[],
            user_message="Hello"
        )
        assert resp.is_success is False
        assert resp.error_code == 408
        assert "timed out" in resp.error.lower()


# ==============================================================================
# 9. Empty Response Handling
# ==============================================================================

@pytest.mark.asyncio
async def test_empty_response_handling():
    """Verify empty response text from Gemini returns a clean error."""
    mock_response = MagicMock()
    mock_response.text = ""
    mock_response.usage_metadata.total_token_count = 0

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("backend.services.gemini_service.get_gemini_client", return_value=mock_client):
        resp = await gemini_service.generate_chat(
            system_instruction="You are ArogyaAI",
            conversation_history=[],
            user_message="Hello"
        )
        assert resp.is_success is False
        assert resp.error_code == 204
        assert "empty response" in resp.error.lower()


# ==============================================================================
# 10. Provider Fallback Routing
# ==============================================================================

@pytest.mark.asyncio
async def test_provider_fallback_routing():
    """Verify that when Gemini fails or provider is set to fallback, LLMService routes cleanly to fallback."""
    # Scenario A: Explicit fallback mode
    with patch.object(settings, "LLM_PROVIDER", "fallback"):
        res = await llm_service.generate_response(
            system_instruction="test",
            conversation_history=[],
            user_message="test"
        )
        assert res.is_fallback is True
        assert res.provider == "fallback"

    # Scenario B: Gemini configured but errors out -> marks is_fallback=True
    with patch.object(settings, "LLM_PROVIDER", "gemini"), \
         patch.object(gemini_service, "generate_chat", return_value=GeminiResponse("", "gemini-2.0-flash", 0, "Rate limit", 429)):
        res = await llm_service.generate_response(
            system_instruction="test",
            conversation_history=[],
            user_message="I have stomach ache."
        )
        assert res.is_fallback is True
        assert res.error == "Rate limit"


# ==============================================================================
# 11. Emergency Detection Supremacy When Gemini Is Unavailable
# ==============================================================================

@pytest.mark.asyncio
async def test_emergency_detection_when_gemini_unavailable():
    """CRITICAL: Emergency detection must immediately intercept before any LLM call, even if Gemini is down."""
    with patch.object(settings, "GEMINI_API_KEY", ""), \
         patch.object(settings, "OPENAI_API_KEY", ""):
        resp = await generate_chat_response(
            user_message="Severe crushing chest pain radiating to left arm with breathlessness and fainting",
            conversation_history=[]
        )
        assert resp.is_emergency is True
        assert resp.safety_flags["emergency_detected"] is True
        assert "112" in resp.content
        assert "102" in resp.content


# ==============================================================================
# 12. RAG Context Integration with Gemini
# ==============================================================================

@pytest.mark.asyncio
async def test_rag_context_integration():
    """Verify that RAG reference passages and citations are passed into Gemini prompts and response containers."""
    mock_llm_result = LLMResult(
        content="According to verified clinical guidelines, stay hydrated and rest.",
        provider="gemini",
        model="gemini-2.0-flash",
        tokens_used=50,
        is_fallback=False
    )

    with patch.object(llm_service, "generate_response", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_llm_result
        resp = await generate_chat_response(
            user_message="What are danger signs for dengue fever?",
            conversation_history=[]
        )
        assert resp.content == mock_llm_result.content
        assert resp.safety_flags["llm_provider"] == "gemini"
        assert len(resp.citations) > 0
        assert any("Dengue" in c["title"] for c in resp.citations)


# ==============================================================================
# 13. Normal Chat Endpoint Integration with Gemini
# ==============================================================================

def test_normal_chat_endpoint_integration(client, authenticated_patient):
    """Verify POST /chat/message works with mock Gemini and persists message."""
    mock_llm_result = LLMResult(
        content="Drink water and rest in a dim room.",
        provider="gemini",
        model="gemini-2.0-flash",
        tokens_used=35,
        is_fallback=False
    )

    with patch.object(llm_service, "generate_response", new_callable=AsyncMock, return_value=mock_llm_result):
        resp = client.post(
            "/chat/message",
            json={"content": "I have mild tension headache."},
            headers=authenticated_patient["headers"]
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["role"] == "assistant"
        assert data["content"] == "Drink water and rest in a dim room."
        assert data["conversation_id"] is not None


# ==============================================================================
# 14. Streaming Chat Endpoint Integration with Gemini
# ==============================================================================

def test_streaming_chat_endpoint_integration(client, authenticated_patient):
    """Verify POST /chat/message/stream streams chunks generated by Gemini via SSE."""
    async def mock_stream_tokens(*args, **kwargs):
        for token in ["Stay ", "hydrated ", "and ", "rest."]:
            yield token, "gemini"

    with patch.object(llm_service, "stream_response", side_effect=mock_stream_tokens):
        resp = client.post(
            "/chat/message/stream",
            json={"content": "Mild body ache after workout."},
            headers=authenticated_patient["headers"]
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "text/event-stream" in resp.headers.get("content-type", "")

        events = []
        for line in resp.text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:"):].strip()))

        event_types = [e.get("type") for e in events]
        assert "start" in event_types
        assert "token" in event_types
        assert "done" in event_types


# ==============================================================================
# 15. Security: No API Keys or Raw Exceptions Exposed in User Responses
# ==============================================================================

def test_no_api_keys_or_raw_exceptions_exposed(client, authenticated_patient):
    """Verify user-facing responses never leak API keys, secret strings, or internal traceback dumps."""
    fake_secret = "AIzaSySecretFakeApiKeyNotForDisplay12345"

    with patch.object(settings, "GEMINI_API_KEY", fake_secret), \
         patch.object(gemini_service, "generate_chat", side_effect=RuntimeError(f"Internal error with key {fake_secret}")):
        resp = client.post(
            "/chat/message",
            json={"content": "I am feeling a little tired."},
            headers=authenticated_patient["headers"]
        )
        assert resp.status_code == status.HTTP_200_OK
        raw_output = resp.text

        # Absolutely no raw key or traceback in response
        assert fake_secret not in raw_output
        assert "Traceback" not in raw_output
        assert "Internal error with key" not in raw_output
