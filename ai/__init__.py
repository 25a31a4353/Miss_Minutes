"""
ai/__init__.py - AI Provider and Reasoning Package.

Exposes the unified AIProvider abstraction, official Gemini provider,
optional Groq fallback provider, deterministic mock provider, and system prompts.
"""

from ai.provider import AIProvider, AIProviderError, ModelConfig, ProviderResponse
from ai.gemini_provider import GeminiProvider
from ai.groq_provider import GroqProvider
from ai.mock_provider import MockAIProvider
from ai.fallback_provider import ResilientAIProvider
from ai.prompts import (
    MISS_MINUTES_SYSTEM_PROMPT,
    JARVIS_SYSTEM_PROMPT,
    INTENT_EXTRACTION_SYSTEM_PROMPT,
)
from ai.schemas import AgentDialogueResponse, StructuredIntent

__all__ = [
    "AIProvider",
    "AIProviderError",
    "ModelConfig",
    "ProviderResponse",
    "GeminiProvider",
    "GroqProvider",
    "MockAIProvider",
    "ResilientAIProvider",
    "MISS_MINUTES_SYSTEM_PROMPT",
    "JARVIS_SYSTEM_PROMPT",
    "INTENT_EXTRACTION_SYSTEM_PROMPT",
    "AgentDialogueResponse",
    "StructuredIntent",
]
