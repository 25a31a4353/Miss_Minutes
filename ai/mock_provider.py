"""
ai/mock_provider.py - Deterministic Mock AI Provider for Safe Testing.

Provides a fast, zero-dependency, deterministic AI provider implementation.
Used in tests, offline environments, and whenever no API keys are configured.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional, Type, TypeVar
from pydantic import BaseModel

from ai.provider import AIProvider, ModelConfig, ProviderResponse

T = TypeVar("T", bound=BaseModel)


class MockAIProvider(AIProvider):
    """
    Deterministic mock AI provider.
    
    Can be configured with fixed responses or dynamic generation hooks
    for text and structured schemas.
    """

    def __init__(
        self,
        default_text_response: str = "Mock AI response.",
        structured_generator: Optional[Callable[[str, Type[T]], T]] = None,
        is_active: bool = True,
    ):
        self._default_text = default_text_response
        self._structured_generator = structured_generator
        self._is_active = is_active
        self.recorded_prompts: list[str] = []

    @property
    def provider_id(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        return self._is_active

    def set_active(self, active: bool) -> None:
        self._is_active = active

    def generate_response(
        self,
        prompt: str,
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        self.recorded_prompts.append(prompt)
        return ProviderResponse(
            content=self._default_text,
            provider_id=self.provider_id,
            model_used="mock-model",
            finish_reason="STOP",
        )

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        config: Optional[ModelConfig] = None,
    ) -> T:
        self.recorded_prompts.append(prompt)
        if self._structured_generator:
            return self._structured_generator(prompt, response_schema)

        if response_schema.__name__ == "StructuredIntent":
            from intents.parser import IntentParser
            import re
            m = re.search(r'Transcript:\s*"([^"]+)"', prompt)
            text = m.group(1) if m else prompt
            return IntentParser()._parse_deterministic(text)

        # Default mock: try creating schema with minimal empty / default fields
        try:
            return response_schema.model_validate({"raw_transcript": prompt})
        except Exception:
            # Try empty dict validation
            try:
                return response_schema.model_validate({})
            except Exception:
                # Construct default instance
                return response_schema.model_construct()

    def generate_stream(
        self,
        prompt: str,
        config: Optional[ModelConfig] = None,
    ):
        self.recorded_prompts.append(prompt)
        words = self._default_text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")

    def generate_chat_response(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        content_summary = " ".join([m.get("content", "") for m in messages])
        self.recorded_prompts.append(content_summary)
        last_msg = messages[-1].get("content", "") if messages else ""
        resp_text = self._default_text
        if "entanglement" in last_msg.lower() and "example" in last_msg.lower():
            resp_text = "Here is a simple example: imagine two matched dice rolling the same number from miles away."
        elif "quantum entanglement" in last_msg.lower():
            resp_text = "Quantum entanglement is a phenomenon where paired particles mirror each other instantly."
        elif "ante enti" in last_msg.lower():
            resp_text = "Quantum entanglement ante rendu particles madhya unna adbhutamaina sambandham."
        elif "songs play cheyyi" in last_msg.lower():
            resp_text = "YouTube lo songs play chestunnanu."

        return ProviderResponse(
            content=resp_text,
            provider_id=self.provider_id,
            model_used="mock-model",
            finish_reason="STOP",
        )

    def generate_chat_stream(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ):
        resp = self.generate_chat_response(messages, config=config)
        words = resp.content.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
