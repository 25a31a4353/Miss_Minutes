"""
security/audit.py - Hardened Security Audit Logging with Secret Redaction & Rotation.

Maintains an immutable in-memory trail and local rotated JSONL audit log of all
security evaluations, verifications, and denials for full governance traceability.

Security Guarantees:
- Never writes API keys, tokens, passwords, or credentials to logs (automatic regex redaction).
- Enforces strict disk bounding via local file rotation (1 MB max file, 2 backups).
- Handles disk errors gracefully without crashing the application.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, asdict
import json
import logging
import os
import re
from typing import Optional
from security.permissions import SecurityDecision, SecurityValidationResult

logger = logging.getLogger(__name__)

# Sensitive patterns that must be sanitized from audit records
SECRET_REDACTION_PATTERNS = [
    re.compile(r"\b(?:sk-[a-zA-Z0-9_\-]{15,}|gsk_[a-zA-Z0-9_\-]{15,})\b"),
    re.compile(r"\bAIza[0-9A-Za-z-_]{20,}\b"),
    re.compile(r"\bghp_[a-zA-Z0-9]{30,}\b"),
    re.compile(r"\b(?:Bearer\s+[a-zA-Z0-9_\-\.]{15,})\b", re.IGNORECASE),
    re.compile(r"(?:password|passwd|secret|token)\s*[:=]\s*([^\s,;]+)", re.IGNORECASE),
]


def redact_sensitive_text(text: Optional[str]) -> Optional[str]:
    """Sanitizes text by stripping out API keys, tokens, and credentials."""
    if not text:
        return text
    sanitized = text
    for pat in SECRET_REDACTION_PATTERNS:
        sanitized = pat.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


@dataclass(frozen=True)
class SecurityAuditEntry:
    """Immutable security audit log record."""
    timestamp: str
    decision: SecurityDecision
    reason: str
    requester: str
    capability: Optional[str] = None
    target_or_query: Optional[str] = None
    event_type: str = "VALIDATION"

    def to_dict(self) -> dict:
        d = {
            "timestamp": self.timestamp,
            "decision": self.decision.value if hasattr(self.decision, "value") else str(self.decision),
            "reason": self.reason,
            "requester": self.requester,
            "capability": self.capability,
            "target_or_query": self.target_or_query,
            "event_type": self.event_type,
        }
        return d


class SecurityAuditLogger:
    """
    Hardened security audit event logger with in-memory bounding,
    automatic credential redaction, and local rotated file sink.
    """

    def __init__(
        self,
        max_entries: int = 500,
        log_file_path: Optional[str] = None,
        max_file_bytes: int = 1_000_000,
        backup_count: int = 2,
    ):
        self._max_entries = max_entries
        self._entries: list[SecurityAuditEntry] = []
        self._log_file_path = log_file_path
        self._max_file_bytes = max_file_bytes
        self._backup_count = backup_count

    @property
    def log_file_path(self) -> Optional[str]:
        return self._log_file_path

    def _rotate_files_if_needed(self) -> None:
        """Rotates log file if it exceeds max_file_bytes."""
        if not self._log_file_path or not os.path.exists(self._log_file_path):
            return

        try:
            if os.path.getsize(self._log_file_path) < self._max_file_bytes:
                return

            for i in range(self._backup_count - 1, 0, -1):
                sfn = f"{self._log_file_path}.{i}"
                dfn = f"{self._log_file_path}.{i + 1}"
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)

            dfn = f"{self._log_file_path}.1"
            if os.path.exists(dfn):
                os.remove(dfn)
            os.rename(self._log_file_path, dfn)
        except Exception as exc:
            logger.debug("Audit log rotation warning: %s", exc)

    def _write_to_disk(self, entry: SecurityAuditEntry) -> None:
        """Appends audit entry to disk safely with error suppression."""
        if not self._log_file_path:
            return

        try:
            log_dir = os.path.dirname(self._log_file_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            self._rotate_files_if_needed()

            with open(self._log_file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except Exception as exc:
            logger.debug("Failed writing to audit file sink: %s", exc)

    def log(
        self,
        result: SecurityValidationResult,
        requester: str = "unknown",
        target_or_query: Optional[str] = None,
        event_type: str = "VALIDATION",
    ) -> SecurityAuditEntry:
        """Records a security validation event with automatic credential redaction."""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        clean_reason = redact_sensitive_text(result.reason) or "Unknown reason"
        clean_target = redact_sensitive_text(target_or_query)

        cap_str = (
            result.capability.value
            if hasattr(result.capability, "value")
            else (str(result.capability) if result.capability else None)
        )

        entry = SecurityAuditEntry(
            timestamp=now_str,
            decision=result.decision,
            reason=clean_reason,
            requester=requester,
            capability=cap_str,
            target_or_query=clean_target,
            event_type=event_type,
        )

        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries.pop(0)

        self._write_to_disk(entry)
        return entry

    def log_event(
        self,
        event_type: str,
        decision: SecurityDecision,
        reason: str,
        requester: str = "system",
        capability: Optional[str] = None,
        target_or_query: Optional[str] = None,
    ) -> SecurityAuditEntry:
        """Direct structured logging of general security and system lifecycle events."""
        res = SecurityValidationResult(
            decision=decision,
            reason=reason,
            capability=capability,
        )
        return self.log(res, requester=requester, target_or_query=target_or_query, event_type=event_type)

    def get_entries(self) -> list[SecurityAuditEntry]:
        """Returns an immutable copy of all in-memory audit entries."""
        return list(self._entries)

    def get_denials(self) -> list[SecurityAuditEntry]:
        """Returns all recorded denial entries."""
        return [e for e in self._entries if e.decision == SecurityDecision.DENY]
