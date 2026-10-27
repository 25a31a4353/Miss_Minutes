"""
agents/message.py - Typed Agent Message Schema & Enums.

Defines the core communication primitives for the Miss Minutes & Jarvis
dual-agent system.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class AgentId(str, Enum):
    """Authoritative agent identities."""
    MISS_MINUTES = "MISS_MINUTES"
    JARVIS = "JARVIS"
    USER = "USER"


class MessageType(str, Enum):
    """Types of inter-agent and agent-user messages."""
    CHAT = "CHAT"                      # Conversational dialogue / banter
    DELEGATION = "DELEGATION"          # Task assignment from peer
    RESULT = "RESULT"                  # Task outcome or computed response
    QUESTION = "QUESTION"              # Clarifying inquiry
    ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"# Receipt confirmation
    NOTIFICATION = "NOTIFICATION"      # Status update
    ERROR = "ERROR"                    # Failure notification
    CANCEL = "CANCEL"                  # Immediate conversation cancellation


class Priority(str, Enum):
    """Message priority levels."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


@dataclass(frozen=True)
class AgentMessage:
    """
    Immutable typed message exchanged between Miss Minutes and Jarvis.
    """
    sender: AgentId
    recipient: AgentId
    message_type: MessageType
    content: str
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    requires_response: bool = False
    parent_message_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def create_reply(
        self,
        sender: AgentId,
        content: str,
        message_type: MessageType = MessageType.RESULT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Helper to create a reply referencing this message's conversation and ID."""
        return AgentMessage(
            sender=sender,
            recipient=self.sender,
            message_type=message_type,
            content=content,
            conversation_id=self.conversation_id,
            parent_message_id=self.message_id,
            priority=self.priority,
            metadata=metadata or {},
        )
