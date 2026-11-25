"""
Unified LLM Provider Abstraction for ArogyaAI (Project ID: 26P_3CSE294)
Selects and manages LLM providers (Google Gemini primary, OpenAI secondary)
with safe fallback routing and uniform interfaces for both streaming and non-streaming modes.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
from openai import AsyncOpenAI
import openai

from backend.config import settings
from backend.services.gemini_service import gemini_service, GeminiResponse

logger = logging.getLogger("arogya_ai.llm_service")

# Optional legacy OpenAI client cache
_openai_client: Optional[AsyncOpenAI] = None


def get_async_openai() -> Optional[AsyncOpenAI]:
    global _openai_client
    if _openai_client is None and settings.OPENAI_API_KEY:
        try:
            _openai_client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=settings.OPENAI_TIMEOUT_SECONDS
            )
        except Exception:
            return None
    return _openai_client


class LLMResult:
    """Standardized response from any LLM provider."""
    def __init__(
        self,
        content: str,
        provider: str,
        model: str,
        tokens_used: int = 0,
        is_fallback: bool = False,
        error: Optional[str] = None
    ):
        self.content = content
        self.provider = provider
        self.model = model
        self.tokens_used = tokens_used
        self.is_fallback = is_fallback
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "is_fallback": self.is_fallback,
            "error": self.error
        }


class LLMService:
    """
    Unified LLM router managing providers according to configuration.
    Routing priority:
    1. settings.LLM_PROVIDER == 'gemini': Google Gen AI SDK.
    2. settings.LLM_PROVIDER == 'openai': AsyncOpenAI.
    3. Any provider error or no keys configured: controlled fallback.
    """

    def __init__(self):
        pass

    @property
    def configured_provider(self) -> str:
        return (settings.LLM_PROVIDER or "gemini").lower().strip()

    async def generate_response(
        self,
        system_instruction: str,
        conversation_history: List[Dict[str, str]],
        user_message: str
    ) -> LLMResult:
        """
        Executes unified non-streaming LLM call.
        Returns LLMResult with provider metadata and fallback indicators.
        """
        provider = self.configured_provider

        # 1. Primary: Google Gemini
        if provider == "gemini":
            try:
                gemini_resp: GeminiResponse = await gemini_service.generate_chat(
                    system_instruction=system_instruction,
                    conversation_history=conversation_history,
                    user_message=user_message,
                    model_name=settings.GEMINI_MODEL
                )
            except Exception as e:
                logger.error(f"[LLM Service] Uncaught exception from Gemini provider: {type(e).__name__}")
                return LLMResult(
                    content="",
                    provider="gemini",
                    model=settings.GEMINI_MODEL,
                    tokens_used=0,
                    is_fallback=True,
                    error="Communication error with Gemini provider."
                )

            if gemini_resp.is_success:
                return LLMResult(
                    content=gemini_resp.content,
                    provider="gemini",
                    model=gemini_resp.model,
                    tokens_used=gemini_resp.tokens_used,
                    is_fallback=False
                )
            else:
                logger.warning(
                    f"[LLM Service] Gemini call failed ({gemini_resp.error}). Routing to clinical fallback."
                )
                return LLMResult(
                    content="",
                    provider="gemini",
                    model=gemini_resp.model,
                    tokens_used=0,
                    is_fallback=True,
                    error=gemini_resp.error
                )

        # 2. Secondary: OpenAI
        elif provider == "openai":
            client = get_async_openai()
            if not client or not settings.OPENAI_API_KEY:
                return LLMResult(
                    content="",
                    provider="openai",
                    model=settings.OPENAI_MODEL,
                    is_fallback=True,
                    error="OpenAI API key not configured."
                )

            messages = [{"role": "system", "content": system_instruction}]
            for turn in conversation_history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role in ["user", "assistant"]:
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": user_message})

            try:
                resp = await client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    temperature=settings.TEMPERATURE,
                    max_tokens=settings.MAX_OUTPUT_TOKENS
                )
                text = resp.choices[0].message.content or ""
                tokens = resp.usage.total_tokens if resp.usage else 0
                return LLMResult(
                    content=text,
                    provider="openai",
                    model=settings.OPENAI_MODEL,
                    tokens_used=tokens,
                    is_fallback=False
                )
            except Exception as e:
                logger.warning(f"[LLM Service] OpenAI call failed: {type(e).__name__}. Routing to fallback.")
                return LLMResult(
                    content="",
                    provider="openai",
                    model=settings.OPENAI_MODEL,
                    is_fallback=True,
                    error=str(e)
                )

        # 3. Explicit Fallback Mode
        return LLMResult(
            content="",
            provider="fallback",
            model="clinical_offline_engine",
            is_fallback=True,
            error="Provider set to fallback mode."
        )

    async def stream_response(
        self,
        system_instruction: str,
        conversation_history: List[Dict[str, str]],
        user_message: str
    ) -> AsyncGenerator[Tuple[str, str], None]:
        """
        Progressively streams token chunks from the active LLM provider.
        Yields tuples of (token_text, provider_name).
        Raises Exception if the provider fails, enabling the caller to trigger fallback.
        """
        provider = self.configured_provider

        # 1. Primary: Google Gemini Streaming
        if provider == "gemini":
            async for token in gemini_service.stream_chat(
                system_instruction=system_instruction,
                conversation_history=conversation_history,
                user_message=user_message,
                model_name=settings.GEMINI_MODEL
            ):
                yield token, "gemini"
            return

        # 2. Secondary: OpenAI Streaming
        elif provider == "openai":
            client = get_async_openai()
            if not client or not settings.OPENAI_API_KEY:
                raise RuntimeError("OpenAI client is not configured for streaming.")

            messages = [{"role": "system", "content": system_instruction}]
            for turn in conversation_history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role in ["user", "assistant"]:
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": user_message})

            stream = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=settings.TEMPERATURE,
                max_tokens=settings.MAX_OUTPUT_TOKENS,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content, "openai"
            return

        # 3. Explicit Fallback
        raise RuntimeError("Provider set to fallback mode.")


llm_service = LLMService()
