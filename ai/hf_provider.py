"""
ai/hf_provider.py - Hugging Face Inference API Provider for Miss Minutes & Jarvis.

Supports:
- Hugging Face Serverless Inference API (InferenceClient)
- Open-access leading open-source models:
  - meta-llama/Llama-3.3-70B-Instruct
  - Qwen/Qwen2.5-72B-Instruct
  - mistralai/Mistral-7B-Instruct-v0.3
- Multilingual reasoning across English, Telugu, and Telugu-English code-switching.
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

DEFAULT_HF_MODEL = "meta-llama/Llama-3.3-70B-Instruct"


class HuggingFaceProvider(AIProvider):
    """
    AI provider for Hugging Face Inference API and router models.
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        default_model: str = DEFAULT_HF_MODEL,
    ):
        self._token = api_token.strip() if api_token and api_token.strip() else None
        self._default_model = default_model
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        """Initializes the Hugging Face InferenceClient if token is present."""
        if not self._token:
            return
        try:
            from huggingface_hub import InferenceClient
            self._client = InferenceClient(token=self._token)
        except Exception as exc:
            logger.warning("Failed to initialize Hugging Face client: %s", exc)
            self._client = None

    @property
    def provider_id(self) -> str:
        return "huggingface"

    def is_available(self) -> bool:
        """Returns True if client is initialized and token is configured."""
        return self._client is not None and bool(self._token)

    def generate_response(
        self,
        prompt: str,
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """Generates text via Hugging Face chat completion interface."""
        if not self.is_available():
            raise AIProviderError("Hugging Face provider is not configured.")

        model = (config.model_name if config and config.model_name else self._default_model)
        temp = config.temperature if config else 0.7
        max_tokens = config.max_tokens if config else 1024

        messages = []
        if config and config.system_instruction:
            messages.append({"role": "system", "content": config.system_instruction})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = self._client.chat_completion(
                messages=messages,
                model=model,
                temperature=temp,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content or ""
            return ProviderResponse(
                content=content,
                provider_id=self.provider_id,
                model_used=model,
                finish_reason=resp.choices[0].finish_reason,
            )
        except Exception as exc:
            logger.error("Hugging Face inference failed: %s", exc)
            raise AIProviderError(f"Hugging Face error: {exc}") from exc

    def generate_chat_response(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """Generates multi-turn chat response."""
        if not self.is_available():
            raise AIProviderError("Hugging Face provider is not configured.")

        model = (config.model_name if config and config.model_name else self._default_model)
        temp = config.temperature if config else 0.7
        max_tokens = config.max_tokens if config else 1024

        payload_msgs = []
        if config and config.system_instruction:
            payload_msgs.append({"role": "system", "content": config.system_instruction})
        for m in messages:
            payload_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})

        try:
            resp = self._client.chat_completion(
                messages=payload_msgs,
                model=model,
                temperature=temp,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content or ""
            return ProviderResponse(
                content=content,
                provider_id=self.provider_id,
                model_used=model,
                finish_reason=resp.choices[0].finish_reason,
            )
        except Exception as exc:
            logger.error("Hugging Face chat error: %s", exc)
            raise AIProviderError(f"Hugging Face chat error: {exc}") from exc

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        config: Optional[ModelConfig] = None,
    ) -> T:
        """Generates structured JSON adhering to Pydantic schema."""
        if not self.is_available():
            raise AIProviderError("Hugging Face provider is not configured.")

        schema_json = json.dumps(response_schema.model_json_schema())
        instruction = (
            (config.system_instruction + "\n" if config and config.system_instruction else "")
            + f"Output strictly valid JSON conforming to this schema without markdown fences:\n{schema_json}"
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
