"""
agents/audit_log.py - Observability & Communication Audit Logging.

Provides a clean, human-readable record of inter-agent exchanges for development
and debugging without logging private credentials.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import List, Optional

from agents.message import AgentMessage


class AgentAuditLogger:
    """
    In-memory and file-based audit logger for dual-agent communication.
    """

    def __init__(self, log_dir: Optional[Path] = None, enabled: bool = True) -> None:
        self._enabled = enabled
        self._entries: List[str] = []
        self._log_file: Optional[Path] = None

        if log_dir:
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                self._log_file = log_dir / "agent_communications.log"
            except OSError:
                self._log_file = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    def log_message(self, message: AgentMessage) -> None:
        """Records an agent message event."""
        if not self._enabled:
            return

        ts_str = datetime.datetime.fromtimestamp(message.timestamp).strftime("%H:%M:%S")
        entry = (
            f"[{ts_str}] [{message.message_type.value}] "
            f"{message.sender.value} -> {message.recipient.value} "
            f"(Conv: {message.conversation_id[:8]}):\n"
            f"  \"{message.content}\""
        )

        self._entries.append(entry)
        # Keep in-memory entries bounded
        if len(self._entries) > 100:
            self._entries = self._entries[-100:]

        if self._log_file:
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(entry + "\n\n")
            except OSError:
                pass

    def get_recent_entries(self, count: int = 20) -> List[str]:
        """Returns the most recent log entries."""
        return list(self._entries[-count:])

    def clear(self) -> None:
        """Clears in-memory log entries."""
        self._entries.clear()
