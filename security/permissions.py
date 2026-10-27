"""
security/permissions.py - Security Decisions and Permission Models.

Defines the core security decisions (ALLOW, DENY, REQUIRES_CONFIRMATION)
and structured audit result models.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field

from actions.schemas import CapabilityType


class SecurityDecision(str, Enum):
    """Tri-state security evaluation decision."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"


class SecurityValidationResult(BaseModel):
    """Result of a security evaluation against an intent or capability request."""
    decision: SecurityDecision = Field(..., description="Evaluation outcome: ALLOW, DENY, or REQUIRES_CONFIRMATION.")
    reason: str = Field(..., description="Human-readable rationale for the security decision.")
    capability: Optional[CapabilityType | str] = Field(None, description="Evaluated capability if applicable.")
    requires_user_prompt: bool = Field(False, description="True if a confirmation dialog must be shown to the user.")
    details: dict[str, Any] = Field(default_factory=dict, description="Diagnostic and audit details.")

    @property
    def is_allowed(self) -> bool:
        return self.decision == SecurityDecision.ALLOW

    @property
    def is_denied(self) -> bool:
        return self.decision == SecurityDecision.DENY

    @property
    def requires_confirmation(self) -> bool:
        return self.decision == SecurityDecision.REQUIRES_CONFIRMATION
