"""
ai/groq_provider.py - Optional Fallback AI Provider using Groq.

Provides an optional OpenAI-compatible fallback adapter for Groq.
The application never depends on Groq being present or active;
it is purely a secondary fallback if Gemini is unreachable.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel

from ai.provider import AIProvider, AIProviderError, ModelConfig, ProviderResponse

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(AIProvider):
    """
    Optional fallback provider leveraging Groq via the OpenAI-compatible SDK.
    
    Guarantees:
    - Never mandatory; application starts and functions with Gemini only or in mock mode.
    - Zero crash when GROQ_API_KEY is not set.
    """

    def __init__(self, api_key: Optional[str] = None, default_model: str = DEFAULT_GROQ_MODEL):
        self._api_key = api_key.strip() if api_key and api_key.strip() else None
        self._default_model = default_model
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        if not self._api_key:
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=GROQ_BASE_URL,
                api_key=self._api_key,
            )
        except Exception as exc:
            logger.warning("Failed to initialize Groq OpenAI-compatible client: %s", exc)
            self._client = None

    @property
    def provider_id(self) -> str:
        return "groq"

    def is_available(self) -> bool:
        """Returns True if Groq API key is configured and client initialized."""
        return self._client is not None and bool(self._api_key)

    def generate_response(
        self,
        prompt: str,
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """Generates text via Groq."""
        if not self.is_available():
            raise AIProviderError("Groq fallback provider is not configured or unavailable.")

        model = (config.model_name if config and config.model_name else self._default_model)
        temp = config.temperature if config else 0.7
        max_tokens = config.max_tokens if config else 1024

        messages = []
        if config and config.system_instruction:
            messages.append({"role": "system", "content": config.system_instruction})
        messages.append({"role": "user", "content": prompt})

        try:
            chat_completion = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temp,
                max_tokens=max_tokens,
            )
            content = chat_completion.choices[0].message.content or ""
            return ProviderResponse(
                content=content,
                provider_id=self.provider_id,
                model_used=model,
                finish_reason=chat_completion.choices[0].finish_reason,
            )
        except Exception as exc:
            logger.error("Groq generation failed: %s", exc)
            raise AIProviderError(f"Groq API error: {exc}") from exc

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        config: Optional[ModelConfig] = None,
    ) -> T:
        """Generates structured JSON using response_format and validates with Pydantic."""
        if not self.is_available():
            raise AIProviderError("Groq fallback provider is not configured or unavailable.")

        model = (config.model_name if config and config.model_name else self._default_model)
        schema_json = json.dumps(response_schema.model_json_schema())
        
        system_instruction = (
            (config.system_instruction + "\n" if config and config.system_instruction else "")
            + f"Output strictly valid JSON matching this schema:\n{schema_json}"
        )

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ]

        try:
            chat_completion = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=config.temperature if config else 0.2,
                response_format={"type": "json_object"},
            )
            content = chat_completion.choices[0].message.content or "{}"
            return response_schema.model_validate_json(content)
        except Exception as exc:
            logger.error("Groq structured output failed: %s", exc)
            raise AIProviderError(f"Groq structured generation error: {exc}") from exc
