"""
ai/openai_provider.py - OpenAI & OpenAI-Compatible AI Provider for Miss Minutes & Jarvis.

Supports:
- Official OpenAI API (GPT-4o, GPT-4o-mini)
- Local open-source inference servers: Ollama (http://localhost:11434/v1), LM Studio, vLLM
- Third-party endpoints: OpenRouter, Together AI, DeepSeek
- Full structured JSON extraction & conversational reasoning in English & Telugu.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel

from ai.provider import AIProvider, AIProviderError, ModelConfig, ProviderResponse

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class OpenAIProvider(AIProvider):
    """
    AI provider for OpenAI and compatible endpoints (Ollama, OpenRouter, etc.).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: str = DEFAULT_OPENAI_MODEL,
    ):
        self._api_key = api_key.strip() if api_key and api_key.strip() else None
        self._base_url = base_url.strip() if base_url and base_url.strip() else None
        self._default_model = default_model
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        """Initializes OpenAI client if API key or custom local base_url is present."""
        if not self._api_key and not self._base_url:
            return
        try:
            from openai import OpenAI
            # If using local Ollama without a key, a dummy key is accepted
            key = self._api_key or "ollama"
            kwargs: dict[str, Any] = {"api_key": key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)
        except Exception as exc:
            logger.warning("Failed to initialize OpenAI client: %s", exc)
            self._client = None

    @property
    def provider_id(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        """Returns True if client is initialized and usable."""
        return self._client is not None

    def generate_response(
        self,
        prompt: str,
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """Generates standard completion via OpenAI API."""
        if not self.is_available():
            raise AIProviderError("OpenAI provider is not configured or client failed to initialize.")

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
            logger.error("OpenAI text generation failed: %s", exc)
            raise AIProviderError(f"OpenAI API error: {exc}") from exc

    def generate_chat_response(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """Generates chat response preserving multi-turn message history."""
        if not self.is_available():
            raise AIProviderError("OpenAI provider is not configured.")

        model = (config.model_name if config and config.model_name else self._default_model)
        temp = config.temperature if config else 0.7
        max_tokens = config.max_tokens if config else 1024

        payload_msgs = []
        if config and config.system_instruction:
            payload_msgs.append({"role": "system", "content": config.system_instruction})
        for m in messages:
            payload_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})

        try:
            chat_completion = self._client.chat.completions.create(
                model=model,
                messages=payload_msgs,
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
            logger.error("OpenAI chat completion failed: %s", exc)
            raise AIProviderError(f"OpenAI chat error: {exc}") from exc

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        config: Optional[ModelConfig] = None,
    ) -> T:
        """Generates structured JSON adhering to Pydantic schema."""
        if not self.is_available():
            raise AIProviderError("OpenAI provider is not configured.")

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
                temperature=config.temperature if config else 0.1,
                response_format={"type": "json_object"},
            )
            content = chat_completion.choices[0].message.content or "{}"
            return response_schema.model_validate_json(content)
        except Exception as exc:
            logger.error("OpenAI structured output failed: %s", exc)
            raise AIProviderError(f"OpenAI structured generation error: {exc}") from exc
