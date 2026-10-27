"""
ai/provider.py - Abstract AI Provider Interface.

Defines the core provider abstraction for Miss Minutes + Jarvis.
All LLM reasoning, structured output generation, and capability planning
must pass through this abstraction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AIProviderError(Exception):
    """Raised when an AI provider fails during inference or configuration."""
    pass


@dataclass(frozen=True)
class ModelConfig:
    """Configuration parameters for AI model generation."""
    model_name: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1024
    system_instruction: Optional[str] = None
    stop_sequences: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderResponse:
    """Standardized response from an AI provider."""
    content: str
    structured_data: Optional[Any] = None
    provider_id: str = "unknown"
    model_used: str = "unknown"
    finish_reason: Optional[str] = None
    usage: dict[str, int] = field(default_factory=dict)


class AIProvider(ABC):
    """
    Abstract Base Class for all AI intelligence providers.
    
    Guarantees:
    - Never crashes the application if an API key is missing or invalid.
    - Provides structured output generation adhering to Pydantic schemas.
    - Keeps provider-specific SDK logic isolated behind this boundary.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier of the provider (e.g. 'gemini', 'groq', 'mock')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider is properly configured and usable."""
        pass

    @abstractmethod
    def generate_response(
        self,
        prompt: str,
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """
        Generates a standard text response for the given prompt.
        
        Raises AIProviderError if generation fails.
        """
        pass

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        config: Optional[ModelConfig] = None,
    ) -> T:
        """
        Generates a structured response adhering to the given Pydantic model.
        
        Raises AIProviderError if generation or validation fails.
        """
        pass

    def generate_stream(
        self,
        prompt: str,
        config: Optional[ModelConfig] = None,
    ):
        """
        Generates a streaming text response (generator yielding chunks).
        Default implementation falls back to complete text generation.
        """
        response = self.generate_response(prompt, config=config)
        yield response.content

    def generate_chat_response(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> ProviderResponse:
        """
        Generates a response from a multi-turn conversation history.
        `messages` is a list of {'role': 'user' | 'assistant' | 'model', 'content': '...'}.
        Default implementation combines messages into a formatted prompt.
        """
        if not messages:
            return self.generate_response("", config=config)
        
        # If single message, treat as prompt
        if len(messages) == 1:
            return self.generate_response(messages[0].get("content", ""), config=config)

        # Formatted multi-turn dialogue
        dialogue_lines = []
        for msg in messages:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "").strip()
            dialogue_lines.append(f"{role}: {content}")
        
        prompt = "\n".join(dialogue_lines) + "\nAssistant:"
        return self.generate_response(prompt, config=config)

    def generate_chat_stream(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ):
        """
        Generates a streaming text response for a multi-turn conversation.
        Default implementation calls generate_chat_response and yields full content.
        """
        resp = self.generate_chat_response(messages, config=config)
        yield resp.content
