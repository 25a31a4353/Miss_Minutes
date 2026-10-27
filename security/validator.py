"""
security/validator.py - Hardened Security Validator, Anti-Injection & Rate Limiter.

Phase 9 Hardening:
1. Master OFFLINE Gate: If the assistant is OFFLINE, all actions/capabilities are strictly DENIED.
2. Default DENY: Any action not in the registered allowlist is DENIED.
3. Anti-Injection Gate: Rejects any attempt to execute shell, PowerShell, CMD,
   registry modifications, arbitrary python scripts, script files (.bat, .ps1, .vbs),
   credential access, or prompt injection override attempts.
4. Tri-State Decision: Returns ALLOW, DENY, or REQUIRES_CONFIRMATION.
5. Local Abuse & Rate Limiting:
   - Sliding-window capability request throttling (max 20 requests / 5s).
   - Cooldown trigger upon repeated security violations (5 consecutive denials -> 10s cooldown).
   - Rapid application launch throttling (max 3 launches of same app / 3s).
"""

from __future__ import annotations

import re
import time
from typing import Any, Optional

from actions.schemas import CapabilityRequest, CapabilityType
from actions.registry import ActionRegistry, CapabilityDescriptor
from actions.apps import resolve_approved_app, is_safe_url
from security.permissions import SecurityDecision, SecurityValidationResult
from security.audit import SecurityAuditLogger

# Patterns indicating malicious attempts to breach the sandbox into shell/system access
DANGEROUS_PATTERNS = [
    re.compile(r"\b(?:powershell|pwsh)\b", re.IGNORECASE),
    re.compile(r"\b(?:cmd(?:\.exe)?|cmd\s*/c)\b", re.IGNORECASE),
    re.compile(r"\b(?:bash|sh|zsh)\b", re.IGNORECASE),
    re.compile(r"\b(?:reg(?:\.exe)?|regedit|winreg|hklm|hkcu)\b", re.IGNORECASE),
    re.compile(r"\b(?:rmdir|del(?:\s+/[a-z]+)*|rm\s+-rf)\b", re.IGNORECASE),
    re.compile(r"\b(?:delete|remove)\s+(?:this\s+)?(?:folder|file|directory|path|system|registry|database)", re.IGNORECASE),
    re.compile(r"\b(?:defender|set-mppreference|disablerealtime|netsh\s+advfirewall|disable-netfirewallrule)\b", re.IGNORECASE),
    re.compile(r"\b(?:python(?:\.exe)?\s+(?:-c|[a-zA-Z0-9_\-\.\/\\]+\.py))\b", re.IGNORECASE),
    re.compile(r"\b(?:curl|wget)\b.*\|.*(?:sh|bash|powershell)", re.IGNORECASE),
    re.compile(r"\b(?:exec|eval|__import__|subprocess)\b", re.IGNORECASE),
    re.compile(r"(?:format\s+[c-z]:)", re.IGNORECASE),
    re.compile(r"open\s+(?:a\s+)?terminal\s+and\s+run", re.IGNORECASE),
    re.compile(r"\b(?:mimikatz|samdump|ntds\.dit|lsass)\b", re.IGNORECASE),
    re.compile(r"\b(?:cmdkey|id_rsa|id_ed25519|\.ssh[\\\/]|credential\s*vault|vaultcmd|passwords?\.txt)\b", re.IGNORECASE),
    # Phase 9: script files and path traversal
    re.compile(r"\b[a-zA-Z0-9_\-\.]+\.(?:bat|cmd|ps1|vbs|wsf|scr|hta)\b", re.IGNORECASE),
    re.compile(r"\b(?:\.\.[\\\/]|[a-zA-Z]:\\windows\\system32\\drivers\\etc\\hosts)\b", re.IGNORECASE),
    # Phase 9: prompt injection override attempts
    re.compile(r"\b(?:ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions|(?:override|bypass|disregard)\s+(?:all\s+)?(?:system\s+prompt|prior\s+directives|security|allowlist|sandbox)|system\s+prompt\s+override)\b", re.IGNORECASE),
]


class SecurityValidator:
    """
    Central security validator governing all capability proposals and requests.
    
    Guarantees:
    - Default DENY: Only allowlisted capabilities can ever pass.
    - OFFLINE authority: When assistant is OFFLINE, evaluation immediately yields DENY.
    - Zero shell execution: All shell / subprocess requests are filtered and permanently blocked.
    - Bounded rate limiting and abuse defense.
    """

    def __init__(
        self,
        registry: Optional[ActionRegistry] = None,
        audit_logger: Optional[SecurityAuditLogger] = None,
        max_requests_per_window: int = 20,
        window_seconds: float = 5.0,
        max_consecutive_denials: int = 5,
        cooldown_seconds: float = 10.0,
        max_rapid_app_launches: int = 3,
        rapid_launch_window: float = 3.0,
    ):
        self._registry = registry or ActionRegistry()
        self._audit = audit_logger or SecurityAuditLogger()
        self._max_requests = max_requests_per_window
        self._window_seconds = window_seconds
        self._max_consecutive_denials = max_consecutive_denials
        self._cooldown_seconds = cooldown_seconds
        self._max_rapid_app_launches = max_rapid_app_launches
        self._rapid_launch_window = rapid_launch_window

        # State tracking for rate limiting & abuse protection
        self._request_timestamps: list[float] = []
        self._consecutive_denials: int = 0
        self._cooldown_until: float = 0.0
        self._app_launch_timestamps: dict[str, list[float]] = {}

    @property
    def audit_logger(self) -> SecurityAuditLogger:
        return self._audit

    def is_in_cooldown(self) -> bool:
        """Returns True if the validator is currently in an abuse-protection cooldown."""
        return time.time() < self._cooldown_until

    def reset_rate_limits(self) -> None:
        """Resets all sliding-window rate limit counters and clears any active cooldown."""
        self._request_timestamps.clear()
        self._consecutive_denials = 0
        self._cooldown_until = 0.0
        self._app_launch_timestamps.clear()

    def is_text_dangerous(self, text: str | None) -> tuple[bool, str]:
        """
        Scans a text payload for forbidden shell commands, registry modifications,
        credential access, or injection patterns. Returns (is_dangerous, matching_reason).
        """
        if not text:
            return False, ""

        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(text):
                return True, f"Blocked forbidden pattern match: '{pattern.pattern}'"

        return False, ""

    def validate_capability_request(
        self,
        request: CapabilityRequest,
        is_assistant_online: bool,
        user_confirmed: bool = False,
    ) -> SecurityValidationResult:
        """
        Evaluates a CapabilityRequest and returns ALLOW, DENY, or REQUIRES_CONFIRMATION.
        """
        # 1. OFFLINE Gate (Absolute Authority)
        if not is_assistant_online:
            res = SecurityValidationResult(
                decision=SecurityDecision.DENY,
                reason="Assistant is currently OFFLINE. All capabilities are strictly locked.",
                capability=request.capability,
            )
            self._audit.log(res, requester=request.requested_by, target_or_query=request.query or request.target, event_type="OFFLINE")
            return res

        now = time.time()

        # 2. Abuse Protection Gate: Active Cooldown Check
        if now < self._cooldown_until:
            rem = max(1, int(self._cooldown_until - now))
            res = SecurityValidationResult(
                decision=SecurityDecision.DENY,
                reason=f"Abuse protection active: Cooldown triggered due to repeated violations ({rem}s remaining).",
                capability=request.capability,
            )
            self._audit.log(res, requester=request.requested_by, target_or_query=request.query or request.target, event_type="RATE_LIMITED")
            return res

        # 3. Rate Limiting: Sliding window total request counter
        self._request_timestamps = [t for t in self._request_timestamps if now - t <= self._window_seconds]
        if len(self._request_timestamps) >= self._max_requests:
            res = SecurityValidationResult(
                decision=SecurityDecision.DENY,
                reason=f"Rate limit exceeded: More than {self._max_requests} capability requests in {self._window_seconds}s.",
                capability=request.capability,
            )
            self._audit.log(res, requester=request.requested_by, target_or_query=request.query or request.target, event_type="RATE_LIMITED")
            return res
        self._request_timestamps.append(now)

        # 4. Allowlist Check
        if not self._registry.is_registered(request.capability):
            self._consecutive_denials += 1
            if self._consecutive_denials >= self._max_consecutive_denials:
                self._cooldown_until = now + self._cooldown_seconds
            res = SecurityValidationResult(
                decision=SecurityDecision.DENY,
                reason=f"Capability '{request.capability}' is not in the approved allowlist.",
                capability=request.capability,
            )
            self._audit.log(res, requester=request.requested_by, target_or_query=request.query or request.target)
            return res

        descriptor = self._registry.get_descriptor(request.capability)

        # 5. Parameter and Payload Inspection (Anti-injection)
        fields_to_check = [request.target, request.query]
        for val in request.parameters.values():
            if isinstance(val, str):
                fields_to_check.append(val)

        for text in fields_to_check:
            is_bad, reason = self.is_text_dangerous(text)
            if is_bad:
                self._consecutive_denials += 1
                if self._consecutive_denials >= self._max_consecutive_denials:
                    self._cooldown_until = now + self._cooldown_seconds
                res = SecurityValidationResult(
                    decision=SecurityDecision.DENY,
                    reason=f"Security violation: {reason}",
                    capability=request.capability,
                )
                self._audit.log(res, requester=request.requested_by, target_or_query=text, event_type="SECURITY_VIOLATION")
                return res

        # 6. Capability-Specific Parameter & Boundary Validation
        cap = request.capability

        # A. SET_VOLUME range check [0, 100]
        if cap == CapabilityType.SET_VOLUME:
            level = request.parameters.get("level")
            if level is None:
                self._consecutive_denials += 1
                res = SecurityValidationResult(
                    decision=SecurityDecision.DENY,
                    reason="SET_VOLUME requires a 'level' parameter.",
                    capability=cap,
                )
                self._audit.log(res, requester=request.requested_by, target_or_query=str(request.parameters))
                return res
            try:
                vol_int = int(level)
            except (ValueError, TypeError):
                self._consecutive_denials += 1
                res = SecurityValidationResult(
                    decision=SecurityDecision.DENY,
                    reason=f"SET_VOLUME level must be an integer, got: {level}",
                    capability=cap,
                )
                self._audit.log(res, requester=request.requested_by, target_or_query=str(level))
                return res

            if vol_int < 0 or vol_int > 100:
                self._consecutive_denials += 1
                res = SecurityValidationResult(
                    decision=SecurityDecision.DENY,
                    reason=f"SET_VOLUME level {vol_int} out of bounds (must be between 0 and 100).",
                    capability=cap,
                )
                self._audit.log(res, requester=request.requested_by, target_or_query=str(vol_int))
                return res

        # B. OPEN_APP allowlist and rapid launch validation
        elif cap == CapabilityType.OPEN_APP:
            app_target = request.target or request.parameters.get("app_name")
            if not app_target or not app_target.strip():
                self._consecutive_denials += 1
                res = SecurityValidationResult(
                    decision=SecurityDecision.DENY,
                    reason="OPEN_APP requires a non-empty application target.",
                    capability=cap,
                )
                self._audit.log(res, requester=request.requested_by, target_or_query="")
                return res

            if any(ch in app_target for ch in ("&", "|", ";", "`", "$", "<", ">", "%", "\n", "\r")):
                self._consecutive_denials += 1
                if self._consecutive_denials >= self._max_consecutive_denials:
                    self._cooldown_until = now + self._cooldown_seconds
                res = SecurityValidationResult(
                    decision=SecurityDecision.DENY,
                    reason=f"Security violation: Application target '{app_target}' contains forbidden shell characters.",
                    capability=cap,
                )
                self._audit.log(res, requester=request.requested_by, target_or_query=app_target, event_type="SECURITY_VIOLATION")
                return res

            resolved = resolve_approved_app(app_target)
            if not resolved:
                self._consecutive_denials += 1
                if self._consecutive_denials >= self._max_consecutive_denials:
                    self._cooldown_until = now + self._cooldown_seconds
                res = SecurityValidationResult(
                    decision=SecurityDecision.DENY,
                    reason=f"Application '{app_target}' is not in the approved application allowlist.",
                    capability=cap,
                )
                self._audit.log(res, requester=request.requested_by, target_or_query=app_target)
                return res

            # Rapid launch throttling for the same application
            app_key = str(app_target).strip().lower()
            prev_launches = [t for t in self._app_launch_timestamps.get(app_key, []) if now - t <= self._rapid_launch_window]
            if len(prev_launches) >= self._max_rapid_app_launches:
                res = SecurityValidationResult(
                    decision=SecurityDecision.DENY,
                    reason=f"Rate limit exceeded: Rapid repeated launch attempts for '{app_target}'.",
                    capability=cap,
                )
                self._audit.log(res, requester=request.requested_by, target_or_query=app_target, event_type="RATE_LIMITED")
                return res
            prev_launches.append(now)
            self._app_launch_timestamps[app_key] = prev_launches

        # C. OPEN_WEBSITE URL safety validation
        elif cap == CapabilityType.OPEN_WEBSITE:
            url_target = request.parameters.get("url") or request.target
            is_safe, url_reason = is_safe_url(url_target)
            if not is_safe:
                self._consecutive_denials += 1
                if self._consecutive_denials >= self._max_consecutive_denials:
                    self._cooldown_until = now + self._cooldown_seconds
                res = SecurityValidationResult(
                    decision=SecurityDecision.DENY,
                    reason=f"URL validation failed: {url_reason}",
                    capability=cap,
                )
                self._audit.log(res, requester=request.requested_by, target_or_query=str(url_target))
                return res

        # D. SEARCH_WEB query validation
        elif cap == CapabilityType.SEARCH_WEB:
            query = request.query or request.target
            if not query or not query.strip():
                self._consecutive_denials += 1
                res = SecurityValidationResult(
                    decision=SecurityDecision.DENY,
                    reason="SEARCH_WEB requires a non-empty search query.",
                    capability=cap,
                )
                self._audit.log(res, requester=request.requested_by, target_or_query="")
                return res

        # E. YouTube search/play phrase validation
        elif cap in (CapabilityType.SEARCH_YOUTUBE, CapabilityType.PLAY_YOUTUBE):
            query = request.query or request.target
            if not query or not query.strip():
                self._consecutive_denials += 1
                res = SecurityValidationResult(
                    decision=SecurityDecision.DENY,
                    reason=f"{cap.value} requires a non-empty search phrase.",
                    capability=cap,
                )
                self._audit.log(res, requester=request.requested_by, target_or_query="")
                return res

        # 7. Confirmation Requirement Check
        if descriptor and descriptor.requires_confirmation and not user_confirmed:
            res = SecurityValidationResult(
                decision=SecurityDecision.REQUIRES_CONFIRMATION,
                reason=f"Operation '{request.capability.value}' requires explicit user confirmation.",
                capability=request.capability,
                requires_user_prompt=True,
            )
            self._audit.log(res, requester=request.requested_by, target_or_query=request.query or request.target)
            return res

        # 8. Permit Operation & Reset Consecutive Denials
        self._consecutive_denials = 0
        res = SecurityValidationResult(
            decision=SecurityDecision.ALLOW,
            reason=f"Capability '{request.capability.value}' verified and permitted.",
            capability=request.capability,
        )
        self._audit.log(res, requester=request.requested_by, target_or_query=request.query or request.target, event_type="ALLOW")
        return res

    def validate_raw_command(self, raw_command: str, is_assistant_online: bool) -> SecurityValidationResult:
        """
        Validates raw textual commands or script strings.
        Always DENIES shell / system injection requests.
        """
        is_bad, reason = self.is_text_dangerous(raw_command)
        if is_bad:
            res = SecurityValidationResult(
                decision=SecurityDecision.DENY,
                reason=f"Command execution forbidden: {reason}",
            )
            self._audit.log(res, requester="user", target_or_query=raw_command, event_type="SECURITY_VIOLATION")
            return res

        # Default Deny: arbitrary raw commands cannot be executed directly
        res = SecurityValidationResult(
            decision=SecurityDecision.DENY,
            reason="Arbitrary command execution is permanently disabled. Only allowlisted typed capabilities are supported.",
        )
        self._audit.log(res, requester="user", target_or_query=raw_command)
        return res
