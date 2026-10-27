"""Agents package for the Miss Minutes & Jarvis dual-agent system."""
from agents.message import AgentId, AgentMessage, MessageType, Priority
from agents.base import Agent
from agents.personalities import (
    AgentPersonality,
    MISS_MINUTES_PERSONALITY,
    JARVIS_PERSONALITY,
)
from agents.context import SharedBoundedContext
from agents.audit_log import AgentAuditLogger
from agents.bus import AgentMessageBus, AgentBusError
from agents.miss_minutes_agent import MissMinutesAgent

def __getattr__(name: str):
    if name in ("Jarvis", "JarvisAgent"):
        from jarvis import Jarvis
        return Jarvis
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AgentId",
    "AgentMessage",
    "MessageType",
    "Priority",
    "Agent",
    "AgentPersonality",
    "MISS_MINUTES_PERSONALITY",
    "JARVIS_PERSONALITY",
    "SharedBoundedContext",
    "AgentAuditLogger",
    "AgentMessageBus",
    "AgentBusError",
    "MissMinutesAgent",
    "Jarvis",
    "JarvisAgent",
]
