"""
Gemini LLM Service for ArogyaAI (Project ID: 26P_3CSE294)
Official Google Gen AI SDK integration for conversational healthcare guidance.
Implements async generation, streaming, bounded retries with exponential backoff,
and safe clinical exception handling.
"""
import asyncio
import logging
import random
from typing import List, Dict, Any, Optional, AsyncGenerator

from google import genai
from google.genai import types
from google.genai import errors

from backend.config import settings

logger = logging.getLogger("arogya_ai.gemini")

_gemini_client: Optional[genai.Client] = None


def get_gemini_client() -> Optional[genai.Client]:
    """
    Returns singleton instance of the official Google Gen AI Client.
    Returns None if GEMINI_API_KEY is not configured.
    """
    global _gemini_client
    api_key = settings.GEMINI_API_KEY.strip() if settings.GEMINI_API_KEY else ""
    if not api_key:
        return None

    if _gemini_client is None:
        try:
            _gemini_client = genai.Client(api_key=api_key)
        except Exception as e:
            logger.error(f"[Gemini Client] Initialization error: {type(e).__name__}")
            return None
    return _gemini_client


def reset_gemini_client() -> None:
    """Resets the singleton client, used for testing and dynamic config reload."""
    global _gemini_client
    _gemini_client = None


def _format_gemini_contents(
    conversation_history: List[Dict[str, str]],
    user_message: str
) -> List[types.Content]:
    """
    Converts conversation history into official Gemini types.Content objects.
    Maps role 'assistant' -> 'model', 'user' -> 'user'.
    """
    contents: List[types.Content] = []

    for turn in conversation_history:
        role = turn.get("role", "")
        text = turn.get("content", "").strip()
        if not text:
            continue

        if role == "user":
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=text)]
                )
            )
        elif role in ["assistant", "model"]:
            contents.append(
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=text)]
                )
            )

    # Append current user prompt
    if user_message.strip():
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message.strip())]
            )
        )

    return contents


class GeminiResponse:
    """Normalized response container from Gemini API."""
    def __init__(
        self,
        content: str,
        model: str,
        tokens_used: int = 0,
        error: Optional[str] = None,
        error_code: Optional[int] = None
    ):
        self.content = content
        self.model = model
        self.tokens_used = tokens_used
        self.error = error
        self.error_code = error_code

    @property
    def is_success(self) -> bool:
        return self.error is None and bool(self.content)


class GeminiService:
    """
    High-level Gemini model interaction service.
    Features:
    - Bounded retries for transient errors (429 rate limit, 503 unavailable).
    - Immediate failure on auth (401/403) or client invalid input (400).
    - Asynchronous streaming and non-streaming execution.
    - Non-leaking technical logging (no API keys, no patient PII).
    """

    def __init__(self):
        self.default_model = settings.GEMINI_MODEL or "gemini-3.5-flash-lite"
        self.timeout_seconds = settings.REQUEST_TIMEOUT
        self.temperature = settings.TEMPERATURE
        self.max_output_tokens = settings.MAX_OUTPUT_TOKENS

    async def verify_model_availability(self, model_name: Optional[str] = None) -> bool:
        """
        Validates if the target Gemini model is accessible with the configured API credentials.
        """
        client = get_gemini_client()
        if not client:
            return False

        target_model = model_name or self.default_model
        try:
            # Query model metadata via async client
            await asyncio.wait_for(
                client.aio.models.get(model=target_model),
                timeout=10.0
            )
            return True
        except Exception as e:
            logger.warning(f"[Gemini Service] Model availability check failed for '{target_model}': {type(e).__name__}")
            return False

    async def generate_chat(
        self,
        system_instruction: str,
        conversation_history: List[Dict[str, str]],
        user_message: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None
    ) -> GeminiResponse:
        """
        Generates a non-streaming conversational response from Gemini.
        Implements bounded exponential backoff for transient errors (max 2 retries).
        """
        client = get_gemini_client()
        if not client:
            return GeminiResponse(
                content="",
                model=self.default_model,
                error="GEMINI_API_KEY is not configured.",
                error_code=401
            )

        target_model = model_name or self.default_model
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature if temperature is not None else self.temperature,
            max_output_tokens=max_output_tokens if max_output_tokens is not None else self.max_output_tokens,
        )

        contents = _format_gemini_contents(conversation_history, user_message)
        max_retries = 2
        delay = 1.0

        for attempt in range(max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=target_model,
                        contents=contents,
                        config=config
                    ),
                    timeout=self.timeout_seconds
                )

                text = response.text if response and response.text else ""
                tokens = 0
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    tokens = getattr(response.usage_metadata, "total_token_count", 0) or 0

                if not text:
                    return GeminiResponse(
                        content="",
                        model=target_model,
                        tokens_used=tokens,
                        error="Empty response received from Gemini model.",
                        error_code=204
                    )

                return GeminiResponse(
                    content=text,
                    model=target_model,
                    tokens_used=tokens
                )

            except errors.APIError as e:
                code = getattr(e, "code", 500)
                # Retry transient errors: 429 (ResourceExhausted) and 503 (Unavailable)
                if code in (429, 503) and attempt < max_retries:
                    jitter = random.uniform(0.1, 0.5)
                    sleep_time = delay + jitter
                    logger.warning(
                        f"[Gemini Transient Error {code}] Attempt {attempt + 1}/{max_retries + 1}. Retrying in {sleep_time:.2f}s..."
                    )
                    await asyncio.sleep(sleep_time)
                    delay *= 2
                    continue

                # Permanent or exhausted error
                error_desc = "Rate limit or quota exceeded" if code == 429 else f"Gemini API error (HTTP {code})"
                logger.error(f"[Gemini APIError] Code: {code}")
                return GeminiResponse(
                    content="",
                    model=target_model,
                    error=error_desc,
                    error_code=code
                )

            except asyncio.TimeoutError:
                logger.warning(f"[Gemini Timeout] Request exceeded {self.timeout_seconds}s limit.")
                return GeminiResponse(
                    content="",
                    model=target_model,
                    error=f"Gemini request timed out after {self.timeout_seconds}s.",
                    error_code=408
                )

            except Exception as e:
                logger.error(f"[Gemini Error] Unexpected exception: {type(e).__name__}")
                return GeminiResponse(
                    content="",
                    model=target_model,
                    error="Internal communication error with Gemini provider.",
                    error_code=500
                )

        return GeminiResponse(
            content="",
            model=target_model,
            error="Maximum retries exhausted.",
            error_code=429
        )

    async def stream_chat(
        self,
        system_instruction: str,
        conversation_history: List[Dict[str, str]],
        user_message: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Progressively streams response tokens from Gemini.
        Yields individual text chunks.
        """
        client = get_gemini_client()
        if not client:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        target_model = model_name or self.default_model
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature if temperature is not None else self.temperature,
            max_output_tokens=max_output_tokens if max_output_tokens is not None else self.max_output_tokens,
        )

        contents = _format_gemini_contents(conversation_history, user_message)

        try:
            stream = await client.aio.models.generate_content_stream(
                model=target_model,
                contents=contents,
                config=config
            )

            async for chunk in stream:
                if chunk and chunk.text:
                    yield chunk.text

        except errors.APIError as e:
            code = getattr(e, "code", 500)
            logger.error(f"[Gemini Stream APIError] Code: {code}")
            raise RuntimeError(f"Gemini streaming error (code: {code})")
        except asyncio.TimeoutError:
            logger.error("[Gemini Stream Timeout]")
            raise RuntimeError("Gemini streaming timed out")
        except Exception as e:
            logger.error(f"[Gemini Stream Error] {type(e).__name__}")
            raise


gemini_service = GeminiService()
