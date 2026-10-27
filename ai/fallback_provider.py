"""
ai/fallback_provider.py - Resilient Multi-Provider Fallback Orchestrator.

Implements graceful failover across AI providers:
Primary (Gemini) -> Secondary (Groq) -> Tertiary (Mock / Safe Local Fallback).

Guarantees:
- Never crashes the application if an API key is missing or invalid.
- Seamlessly falls back upon network failure, rate limits (HTTP 429), or API errors.
- Clearly flags which provider actually generated the response.
- Fully compatible with the AIProvider abstraction.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, List, Optional, Type, TypeVar
from pydantic import BaseModel

from ai.provider import AIProvider, AIProviderError, ModelConfig, ProviderResponse

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class ResilientAIProvider(AIProvider):
    """
    Orchestrates failover across multiple AI providers in order of preference.
    Default hierarchy: Gemini -> Groq -> MockProvider.
    """

    def __init__(
        self,
        primary: Optional[AIProvider] = None,
        secondary: Optional[AIProvider] = None,
        fallback: Optional[AIProvider] = None,
    ):
        self.primary = primary
        self.secondary = secondary
        self.fallback = fallback

    @property
    def provider_id(self) -> str:
        # Returns active provider id if available
        if self.primary and self.primary.is_available():
            return f"resilient({self.primary.provider_id})"
        if self.secondary and self.secondary.is_available():
            return f"resilient({self.secondary.provider_id})"
        if self.fallback and self.fallback.is_available():
            return f"resilient({self.fallback.provider_id})"
        return "resilient(unavailable)"

    def is_available(self) -> bool:
        """Returns True if at least one underlying provider is available."""
        return any(
            p is not None and p.is_available()
            for p in (self.primary, self.secondary, self.fallback)
        )

    def _get_candidate_chain(self) -> List[AIProvider]:
        """Returns available providers in strict priority order."""
        candidates = []
        for p in (self.primary, self.secondary, self.fallback):
            if p is not None and p.is_available():
                candidates.append(p)
        return candidates

    def generate_response(
        self,
        prompt: str,
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """Attempts text generation through priority chain with automatic failover."""
        candidates = self._get_candidate_chain()
        if not candidates:
            raise AIProviderError("No AI provider is available in the fallback chain.")

        last_err: Optional[Exception] = None
        for provider in candidates:
            try:
                resp = provider.generate_response(prompt, config=config)
                return resp
            except Exception as exc:
                last_err = exc
                logger.warning(
                    "Provider %s failed (%s); attempting next candidate in fallback chain.",
                    provider.provider_id,
                    exc,
                )

        raise AIProviderError(f"All providers in fallback chain failed. Last error: {last_err}") from last_err

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        config: Optional[ModelConfig] = None,
    ) -> T:
        """Attempts structured output generation through priority chain with automatic failover."""
        candidates = self._get_candidate_chain()
        if not candidates:
            raise AIProviderError("No AI provider is available for structured extraction.")

        last_err: Optional[Exception] = None
        for provider in candidates:
            try:
                return provider.generate_structured(prompt, response_schema=response_schema, config=config)
            except Exception as exc:
                last_err = exc
                logger.warning(
                    "Structured generation on %s failed (%s); attempting next candidate.",
                    provider.provider_id,
                    exc,
                )

        raise AIProviderError(f"All providers failed structured extraction. Last error: {last_err}") from last_err

    def generate_stream(
        self,
        prompt: str,
        config: Optional[ModelConfig] = None,
    ) -> Iterator[str]:
        """Attempts streaming through priority chain with automatic failover."""
        candidates = self._get_candidate_chain()
        if not candidates:
            raise AIProviderError("No AI provider available for streaming.")

        last_err: Optional[Exception] = None
        for provider in candidates:
            try:
                yield from provider.generate_stream(prompt, config=config)
                return
            except Exception as exc:
                last_err = exc
                logger.warning(
                    "Streaming on %s failed (%s); attempting next candidate in fallback chain.",
                    provider.provider_id,
                    exc,
                )

        raise AIProviderError(f"All providers in streaming chain failed: {last_err}") from last_err

    def generate_chat_response(
        self,
        messages: List[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """Attempts multi-turn chat generation with automatic failover."""
        candidates = self._get_candidate_chain()
        if not candidates:
            raise AIProviderError("No AI provider available for multi-turn chat.")

        last_err: Optional[Exception] = None
        for provider in candidates:
            try:
                return provider.generate_chat_response(messages, config=config)
            except Exception as exc:
                last_err = exc
                logger.warning(
                    "Multi-turn chat on %s failed (%s); attempting next candidate.",
                    provider.provider_id,
                    exc,
                )

        raise AIProviderError(f"All providers in chat chain failed: {last_err}") from last_err

    def generate_chat_stream(
        self,
        messages: List[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> Iterator[str]:
        """Attempts streaming multi-turn chat generation with automatic failover."""
        candidates = self._get_candidate_chain()
        if not candidates:
            raise AIProviderError("No AI provider available for chat streaming.")

        last_err: Optional[Exception] = None
        for provider in candidates:
            try:
                yield from provider.generate_chat_stream(messages, config=config)
                return
            except Exception as exc:
                last_err = exc
                logger.warning(
                    "Chat streaming on %s failed (%s); attempting next candidate.",
                    provider.provider_id,
                    exc,
                )

        raise AIProviderError(f"All providers in chat stream chain failed: {last_err}") from last_err
