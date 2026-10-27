"""
ai/gemini_provider.py - Official Google GenAI Python SDK Provider.

Primary intelligence provider for Miss Minutes + Jarvis using `google-genai`.
Supports text generation, structured outputs (Pydantic models),
and conversational reasoning across English and Telugu.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Iterator, List, Optional, Type, TypeVar
from pydantic import BaseModel

from ai.provider import AIProvider, AIProviderError, ModelConfig, ProviderResponse

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class GeminiProvider(AIProvider):
    """
    Primary AI provider leveraging Google Gemini via the official `google-genai` SDK.
    
    Guarantees:
    - Never raises unhandled SDK exceptions into application lifecycle.
    - Gracefully indicates unavailability if GEMINI_API_KEY is unset.
    - Implements structured JSON schema outputs with Pydantic validation.
    - Supports real-time text streaming and multi-turn bounded chat conversations.
    """

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self._api_key = api_key.strip() if api_key and api_key.strip() else None
        env_model = os.environ.get("GEMINI_MODEL", "").strip()
        self._default_model = default_model or env_model or DEFAULT_GEMINI_MODEL
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        """Initializes the google-genai Client if an API key is present."""
        if not self._api_key:
            return
        try:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        except Exception as exc:
            logger.warning("Failed to initialize google-genai Client: %s", exc)
            self._client = None

    @property
    def provider_id(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        """Returns True if the provider has an initialized client and API key."""
        return self._client is not None and bool(self._api_key)

    def generate_response(
        self,
        prompt: str,
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """Generates a text completion from Gemini."""
        if not self.is_available():
            raise AIProviderError("Gemini provider is not configured or unavailable.")

        from google.genai import types

        model = (config.model_name if config and config.model_name else self._default_model)
        temp = config.temperature if config else 0.7
        max_tokens = config.max_tokens if config else 1024
        system_instruction = config.system_instruction if config else None

        gen_config = types.GenerateContentConfig(
            temperature=temp,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
            stop_sequences=config.stop_sequences if config else None,
        )

        try:
            response = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config=gen_config,
            )
            text_content = response.text or ""
            return ProviderResponse(
                content=text_content,
                provider_id=self.provider_id,
                model_used=model,
                finish_reason="STOP",
            )
        except Exception as exc:
            logger.error("Gemini text generation failed: %s", exc)
            raise AIProviderError(f"Gemini generation error: {exc}") from exc

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        config: Optional[ModelConfig] = None,
    ) -> T:
        """Generates a structured Pydantic object from Gemini using response_schema."""
        if not self.is_available():
            raise AIProviderError("Gemini provider is not configured or unavailable.")

        from google.genai import types

        model = (config.model_name if config and config.model_name else self._default_model)
        temp = config.temperature if config else 0.2  # Lower temperature for structured extraction
        system_instruction = config.system_instruction if config else None

        gen_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=temp,
            system_instruction=system_instruction,
        )

        try:
            response = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config=gen_config,
            )
            # When response_schema is provided, google-genai parses it into response.parsed
            if hasattr(response, "parsed") and response.parsed is not None:
                if isinstance(response.parsed, response_schema):
                    return response.parsed
                # If parsed as a dict:
                if isinstance(response.parsed, dict):
                    return response_schema.model_validate(response.parsed)

            # Fallback parsing raw text JSON
            raw_text = response.text or "{}"
            return response_schema.model_validate_json(raw_text)
        except Exception as exc:
            logger.error("Gemini structured generation failed: %s", exc)
            raise AIProviderError(f"Gemini structured generation error: {exc}") from exc

    def generate_stream(
        self,
        prompt: str,
        config: Optional[ModelConfig] = None,
    ) -> Iterator[str]:
        """Generates a streaming text response from Gemini."""
        if not self.is_available():
            raise AIProviderError("Gemini provider is not configured or unavailable.")

        from google.genai import types

        model = (config.model_name if config and config.model_name else self._default_model)
        temp = config.temperature if config else 0.7
        max_tokens = config.max_tokens if config else 1024
        system_instruction = config.system_instruction if config else None

        gen_config = types.GenerateContentConfig(
            temperature=temp,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
            stop_sequences=config.stop_sequences if config else None,
        )

        try:
            stream = self._client.models.generate_content_stream(
                model=model,
                contents=prompt,
                config=gen_config,
            )
            for chunk in stream:
                chunk_text = getattr(chunk, "text", "") or ""
                if chunk_text:
                    yield chunk_text
        except Exception as exc:
            logger.error("Gemini stream generation failed: %s", exc)
            raise AIProviderError(f"Gemini streaming error: {exc}") from exc

    def generate_chat_response(
        self,
        messages: List[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """Generates a response from a multi-turn conversation history."""
        if not self.is_available():
            raise AIProviderError("Gemini provider is not configured or unavailable.")

        from google.genai import types

        model = (config.model_name if config and config.model_name else self._default_model)
        temp = config.temperature if config else 0.7
        max_tokens = config.max_tokens if config else 1024
        system_instruction = config.system_instruction if config else None

        gen_config = types.GenerateContentConfig(
            temperature=temp,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
            stop_sequences=config.stop_sequences if config else None,
        )

        contents: List[Any] = []
        for msg in messages:
            role_raw = msg.get("role", "user").lower()
            role = "user" if role_raw in ("user", "human") else "model"
            content_text = msg.get("content", "")
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=content_text)],
                )
            )

        try:
            response = self._client.models.generate_content(
                model=model,
                contents=contents,
                config=gen_config,
            )
            text_content = response.text or ""
            return ProviderResponse(
                content=text_content,
                provider_id=self.provider_id,
                model_used=model,
                finish_reason="STOP",
            )
        except Exception as exc:
            logger.error("Gemini multi-turn generation failed: %s", exc)
            raise AIProviderError(f"Gemini multi-turn error: {exc}") from exc

    def generate_chat_stream(
        self,
        messages: List[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> Iterator[str]:
        """Generates a streaming text response from a multi-turn conversation."""
        if not self.is_available():
            raise AIProviderError("Gemini provider is not configured or unavailable.")

        from google.genai import types

        model = (config.model_name if config and config.model_name else self._default_model)
        temp = config.temperature if config else 0.7
        max_tokens = config.max_tokens if config else 1024
        system_instruction = config.system_instruction if config else None

        gen_config = types.GenerateContentConfig(
            temperature=temp,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
            stop_sequences=config.stop_sequences if config else None,
        )

        contents: List[Any] = []
        for msg in messages:
            role_raw = msg.get("role", "user").lower()
            role = "user" if role_raw in ("user", "human") else "model"
            content_text = msg.get("content", "")
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=content_text)],
                )
            )

        try:
            stream = self._client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=gen_config,
            )
            for chunk in stream:
                chunk_text = getattr(chunk, "text", "") or ""
                if chunk_text:
                    yield chunk_text
        except Exception as exc:
            logger.error("Gemini multi-turn stream failed: %s", exc)
            raise AIProviderError(f"Gemini multi-turn streaming error: {exc}") from exc
