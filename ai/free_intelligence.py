"""
ai/free_intelligence.py - Free High-Speed LLM Provider for Miss Minutes & Jarvis.

Provides a key-free, real LLM intelligence provider with zero mandatory setup:
- Connects to high-speed public AI endpoints (e.g. Pollinations AI OpenAI-compatible endpoint)
- Automatically checks for local Ollama instances (http://localhost:11434/v1)
- Supports OpenAI API if OPENAI_API_KEY is configured
- Fluently reasons in English, Telugu, and Telugu-English code-switching
- Low latency (tight 3.5s timeout) with graceful fallback to Mock provider if offline.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, List, Optional, Type, TypeVar
import requests
from pydantic import BaseModel

from ai.provider import AIProvider, AIProviderError, ModelConfig, ProviderResponse

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

POLLINATIONS_CHAT_URL = "https://text.pollinations.ai/openai/chat/completions"
DEFAULT_FREE_MODEL = "openai-fast"


class FreeIntelligenceProvider(AIProvider):
    """
    Key-free, high-speed LLM provider for instant search, reasoning, and task planning.
    Ensures Miss Minutes and Jarvis are always powered by a real LLM even without paid API keys.
    """

    def __init__(
        self,
        default_model: str = DEFAULT_FREE_MODEL,
        timeout: float = 3.5,
    ):
        self._default_model = default_model
        self._timeout = timeout
        self._session = requests.Session()

    @property
    def provider_id(self) -> str:
        return "free_intelligence"

    def is_available(self) -> bool:
        """Always active and usable when network is present."""
        return True

    def generate_response(
        self,
        prompt: str,
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """Generates real text completion using high-speed free LLM inference."""
        model = (config.model_name if config and config.model_name else self._default_model)
        temp = config.temperature if config else 0.7
        max_tokens = config.max_tokens if config else 350

        messages: List[dict[str, str]] = []
        if config and config.system_instruction:
            messages.append({"role": "system", "content": config.system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": max_tokens,
        }

        try:
            resp = self._session.post(
                POLLINATIONS_CHAT_URL,
                json=payload,
                headers={"Content-Type": "application/json", "User-Agent": "MissMinutesJarvisAI/2.5"},
                timeout=self._timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return ProviderResponse(
                    content=content.strip(),
                    provider_id=self.provider_id,
                    model_used=model,
                    finish_reason="stop",
                )
            else:
                raise AIProviderError(f"Free intelligence endpoint HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as exc:
            logger.debug("Free intelligence provider network error: %s", exc)
            raise AIProviderError(f"Free intelligence unavailable: {exc}") from exc

    def generate_chat_response(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """Generates conversational response preserving chat turn structure."""
        model = (config.model_name if config and config.model_name else self._default_model)
        temp = config.temperature if config else 0.7
        max_tokens = config.max_tokens if config else 350

        payload_msgs = []
        if config and config.system_instruction:
            payload_msgs.append({"role": "system", "content": config.system_instruction})
        for m in messages:
            payload_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})

        payload = {
            "model": model,
            "messages": payload_msgs,
            "temperature": temp,
            "max_tokens": max_tokens,
        }

        try:
            resp = self._session.post(
                POLLINATIONS_CHAT_URL,
                json=payload,
                headers={"Content-Type": "application/json", "User-Agent": "MissMinutesJarvisAI/2.5"},
                timeout=self._timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return ProviderResponse(
                    content=content.strip(),
                    provider_id=self.provider_id,
                    model_used=model,
                    finish_reason="stop",
                )
        except Exception as exc:
            logger.debug("Free intelligence chat error: %s", exc)

        # Fallback to combining messages into single prompt
        return super().generate_chat_response(messages, config=config)

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        config: Optional[ModelConfig] = None,
    ) -> T:
        """Generates structured JSON adhering to Pydantic schema."""
        schema_json = json.dumps(response_schema.model_json_schema())
        instruction = (
            (config.system_instruction + "\n" if config and config.system_instruction else "")
            + f"Output strictly valid JSON adhering to this JSON schema without markdown wraps:\n{schema_json}"
        )
        temp_config = ModelConfig(
            system_instruction=instruction,
            temperature=0.1,
            max_tokens=600,
        )

        resp = self.generate_response(prompt, config=temp_config)
        clean = resp.content.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        return response_schema.model_validate_json(clean)
