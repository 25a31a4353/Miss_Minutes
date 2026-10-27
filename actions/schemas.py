"""
actions/schemas.py - Typed Capability Schemas.

Defines the strictly allowlisted capabilities and typed request/result structures.
NO arbitrary shell, PowerShell, or subprocess command structures exist in this schema.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class CapabilityType(str, Enum):
    """Explicit allowlist of permitted system capabilities."""
    OPEN_APP = "OPEN_APP"
    OPEN_WEBSITE = "OPEN_WEBSITE"
    SEARCH_WEB = "SEARCH_WEB"
    SEARCH_YOUTUBE = "SEARCH_YOUTUBE"
    PLAY_YOUTUBE = "PLAY_YOUTUBE"
    GET_TIME = "GET_TIME"
    GET_SYSTEM_STATUS = "GET_SYSTEM_STATUS"
    GET_BATTERY_STATUS = "GET_BATTERY_STATUS"
    GET_VOLUME = "GET_VOLUME"
    SET_VOLUME = "SET_VOLUME"
    VOLUME_UP = "VOLUME_UP"
    VOLUME_DOWN = "VOLUME_DOWN"
    VOLUME_MUTE = "VOLUME_MUTE"
    MEDIA_PLAY_PAUSE = "MEDIA_PLAY_PAUSE"
    MEDIA_NEXT = "MEDIA_NEXT"
    MEDIA_PREVIOUS = "MEDIA_PREVIOUS"
    READ_SCREEN = "READ_SCREEN"
    RESEARCH_EXPLAIN = "RESEARCH_EXPLAIN"


class CapabilityRequest(BaseModel):
    """
    Typed, structured request to perform an approved system capability.
    
    Guarantees:
    - Never accepts raw shell or PowerShell command strings.
    - Carries requester identity and unique tracking ID.
    - Parameters are strictly validated against the capability definition.
    """
    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique UUID tracking this capability invocation.",
    )
    capability: CapabilityType = Field(
        ...,
        description="The allowlisted capability to execute.",
    )
    target: Optional[str] = Field(
        default=None,
        description="Target resource (e.g. 'youtube', 'chrome').",
    )
    query: Optional[str] = Field(
        default=None,
        description="Search query or media search phrase.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Strongly-typed arguments specific to the capability.",
    )
    requested_by: str = Field(
        default="jarvis",
        description="Agent proposing this capability execution.",
    )


class CapabilityResult(BaseModel):
    """Execution result returned by a capability executor."""
    request_id: str = Field(..., description="Matching request UUID.")
    capability: CapabilityType = Field(..., description="Executed capability.")
    success: bool = Field(..., description="Whether the action succeeded.")
    output: Any = Field(default=None, description="Output data or payload.")
    error_message: Optional[str] = Field(default=None, description="Error detail if failed.")
    simulated: bool = Field(
        default=True,
        description="True if execution was simulated/mocked for safety.",
    )
    verified: bool = Field(
        default=False,
        description="True if execution outcome was independently verified.",
    )
