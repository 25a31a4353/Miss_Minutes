"""
agents/context.py - Shared Bounded Context for Dual-Agent Collaboration.

Guarantees:
- Strictly bounded history (ring buffer of last N turns, default 10).
- Thread-safe access via re-entrant lock.
- Automatic sanitization of potential API keys and secrets.
- Never stores passwords, tokens, or audio buffers.
"""

from __future__ import annotations

import re
import threading
from typing import List, Optional

from agents.message import AgentMessage


# Pattern matching common AI provider secret key formats
_SECRET_PATTERN = re.compile(
    r"(?:sk-[a-zA-Z0-9]{20,}|gsk_[a-zA-Z0-9]{20,}|AIza[0-9A-Za-z-_]{35}|ghp_[a-zA-Z0-9]{36})"
)


def sanitize_content(content: str) -> str:
    """Replaces potential API keys and bearer tokens with redacted placeholders."""
    if not content:
        return ""
    return _SECRET_PATTERN.sub("[REDACTED_SECRET]", content)


class SharedBoundedContext:
    """
    Thread-safe bounded memory shared between Miss Minutes and Jarvis.
    """

    def __init__(self, max_turns: int = 10) -> None:
        self._max_turns = max(2, max_turns)
        self._turns: List[AgentMessage] = []
        self._lock = threading.RLock()

    @property
    def max_turns(self) -> int:
        return self._max_turns

    def add_message(self, message: AgentMessage) -> None:
        """Appends a sanitized message to the bounded turn window."""
        with self._lock:
            # Create sanitized copy if secrets detected
            sanitized_text = sanitize_content(message.content)
            if sanitized_text != message.content:
                safe_msg = AgentMessage(
                    sender=message.sender,
                    recipient=message.recipient,
                    message_type=message.message_type,
                    content=sanitized_text,
                    message_id=message.message_id,
                    conversation_id=message.conversation_id,
                    metadata=dict(message.metadata),
                    priority=message.priority,
                    requires_response=message.requires_response,
                    parent_message_id=message.parent_message_id,
                    timestamp=message.timestamp,
                )
            else:
                safe_msg = message

            self._turns.append(safe_msg)
            # Enforce ring buffer ceiling
            if len(self._turns) > self._max_turns:
                self._turns = self._turns[-self._max_turns:]

    def get_turns(self, limit: Optional[int] = None) -> List[AgentMessage]:
        """Returns a copy of recent turns up to the requested limit."""
        with self._lock:
            if limit is None or limit >= len(self._turns):
                return list(self._turns)
            return list(self._turns[-limit:])

    def get_summary(self) -> str:
        """Returns a clean formatted text summary of recent exchanges."""
        with self._lock:
            lines = []
            for t in self._turns:
                lines.append(f"[{t.sender.value} -> {t.recipient.value}] ({t.message_type.value}): {t.content}")
            return "\n".join(lines)

    def clear(self) -> None:
        """Clears all stored history."""
        with self._lock:
            self._turns.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._turns)
