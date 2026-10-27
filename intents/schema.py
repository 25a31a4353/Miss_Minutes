"""
intents/schema.py - Structured Intent Schema for Multilingual NLP.

Defines Pydantic models for intent classification, language detection,
code-switching awareness, and entity extraction across English and Telugu.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """Categorized user intent types."""
    CHAT = "CHAT"
    QUESTION = "QUESTION"
    SEARCH_WEB = "SEARCH_WEB"
    OPEN_WEBSITE = "OPEN_WEBSITE"
    OPEN_APP = "OPEN_APP"
    PLAY_MEDIA = "PLAY_MEDIA"
    GET_TIME = "GET_TIME"
    GET_SYSTEM_STATUS = "GET_SYSTEM_STATUS"
    GET_BATTERY_STATUS = "GET_BATTERY_STATUS"
    GET_VOLUME = "GET_VOLUME"
    SET_VOLUME = "SET_VOLUME"
    VOLUME_UP = "VOLUME_UP"
    VOLUME_DOWN = "VOLUME_DOWN"
    VOLUME_MUTE = "VOLUME_MUTE"
    MEDIA_PLAY_PAUSE = "MEDIA_PLAY_PAUSE"
    READ_SCREEN = "READ_SCREEN"
    RESEARCH_EXPLAIN = "RESEARCH_EXPLAIN"
    QUIET_STANDBY = "QUIET_STANDBY"
    RESUME_LISTENING = "RESUME_LISTENING"
    DELEGATE_TO_JARVIS = "DELEGATE_TO_JARVIS"
    DELEGATE_TO_MISS_MINUTES = "DELEGATE_TO_MISS_MINUTES"
    CANCEL = "CANCEL"
    UNKNOWN = "UNKNOWN"


class LanguageCode(str, Enum):
    """Detected language categories including Telugu-English code-switching."""
    EN = "en"
    TE = "te"
    TE_EN = "te-en"
    UNKNOWN = "unknown"


class IntentEntities(BaseModel):
    """Extracted entities from a user utterance."""
    query: Optional[str] = Field(
        default=None,
        description="Search query, media title, or question subject.",
    )
    target: Optional[str] = Field(
        default=None,
        description="Target platform, domain, or device (e.g. 'youtube', 'chrome').",
    )
    app_name: Optional[str] = Field(
        default=None,
        description="Name of the desktop application (e.g. 'notepad', 'calc').",
    )
    website_url: Optional[str] = Field(
        default=None,
        description="Specific website URL if explicitly provided.",
    )
    volume_level: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Target volume level from 0 to 100.",
    )
    additional_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured parameters extracted from the utterance.",
    )


class StructuredIntent(BaseModel):
    """
    Normalized, structured intent extracted from user speech or text.
    
    Guarantees:
    - Preserves the verbatim raw transcript.
    - Captures language and code-switching without early forced translation.
    - Specifies whether desktop capability execution is required.
    - Recommends the appropriate agent (Miss Minutes vs. Jarvis).
    """
    intent: IntentType = Field(
        default=IntentType.UNKNOWN,
        description="Primary classified intent.",
    )
    language: LanguageCode = Field(
        default=LanguageCode.EN,
        description="Detected language of the transcript.",
    )
    raw_transcript: str = Field(
        ...,
        description="Verbatim user utterance, unmodified.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Classification confidence score.",
    )
    entities: IntentEntities = Field(
        default_factory=IntentEntities,
        description="Extracted entities.",
    )
    requires_action: bool = Field(
        default=False,
        description="Whether this intent requests desktop/system capability execution.",
    )
    preferred_agent: str = Field(
        default="miss_minutes",
        description="Recommended handling agent ('miss_minutes' or 'jarvis').",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Optional brief explanation of the intent classification.",
    )
