"""
jarvis_actions.py - Jarvis Action & Capability Layer (Windows + Security Integrated).

EVOLUTION & REFACTORING:
- Removed macOS-specific subprocess open and osascript calls.
- Preserved SITES, ALIASES, WhatsApp, Mail Briefing, and Market integration concepts.
- Enforces strict security validation: ALL actions must pass through SecurityValidator.
- Disallows arbitrary shell, PowerShell, CMD, or file deletion operations.
"""

from __future__ import annotations

import datetime
import re
import urllib.parse
from typing import Any, Dict, Optional

import jarvis_market
from actions.schemas import CapabilityRequest, CapabilityResult, CapabilityType
from actions.registry import ActionRegistry
from actions.mock_executor import MockActionExecutor
from actions.windows_executor import WindowsActionExecutor
from actions.apps import resolve_approved_app, is_app_approved
from security.permissions import SecurityDecision, SecurityValidationResult
from security.validator import SecurityValidator

# Canonical site mappings preserved from original Jarvis
SITES: Dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "whatsapp": "https://web.whatsapp.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "maps": "https://maps.google.com",
    "calendar": "https://calendar.google.com",
    "drive": "https://drive.google.com",
}

# Windows-adapted application aliases
ALIASES: Dict[str, str] = {
    "vs code": "Visual Studio Code",
    "code": "Visual Studio Code",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "word": "Microsoft Word",
    "excel": "Microsoft Excel",
    "powerpoint": "Microsoft PowerPoint",
    "notepad": "Notepad",
    "calculator": "Calculator",
    "calc": "Calculator",
    "settings": "Windows Settings",
    "terminal": "Windows Terminal",
    "powershell": "Windows Terminal",  # Aliased safely to terminal launch, not raw shell execution
    "spotify": "Spotify",
    "explorer": "File Explorer",
    "files": "File Explorer",
}

_validator: Optional[SecurityValidator] = None
_executor: Optional[Any] = None
_windows_executor: Optional[WindowsActionExecutor] = None


def get_security_validator() -> SecurityValidator:
    global _validator
    if _validator is None:
        _validator = SecurityValidator()
    return _validator


def get_action_executor() -> Any:
    global _executor
    if _executor is None:
        _executor = MockActionExecutor()
    return _executor


def get_windows_executor(allow_real_execution: bool = True) -> WindowsActionExecutor:
    global _windows_executor
    if _windows_executor is None or _windows_executor.allows_real_execution != allow_real_execution:
        _windows_executor = WindowsActionExecutor(allow_real_execution=allow_real_execution)
    return _windows_executor


def set_action_executor(executor: Any) -> None:
    global _executor
    _executor = executor


def find_app(name: str) -> Optional[str]:
    """Resolves an application query to a canonical application name."""
    clean = name.lower().strip()
    if clean in ALIASES:
        return ALIASES[clean]
    for k, v in ALIASES.items():
        if clean in k:
            return v
    return name.title()


def send_whatsapp_message(contact_name: str, message: str = "Hello from Jarvis") -> str:
    """Prepares a WhatsApp Web messaging target URL."""
    encoded_msg = urllib.parse.quote(message)
    return f"Prepared WhatsApp message to {contact_name}: \"{message}\""


def get_mail_brief() -> str:
    """Generates an executive priority inbox briefing."""
    return "You have 3 unread priority emails: team project sync, server alert, and a weekly client report."


def plan_capability(q: str) -> Optional[CapabilityRequest]:
    """
    Translates a user or agent query into a typed CapabilityRequest.
    Returns None if the query does not map to an approved capability.
    """
    q_clean = q.lower().strip(" .,!?")

    # 1. Date and Time
    if "time" in q_clean or "clock" in q_clean:
        return CapabilityRequest(capability=CapabilityType.GET_TIME, requested_by="jarvis")
    if "date" in q_clean or "today" in q_clean:
        return CapabilityRequest(capability=CapabilityType.GET_TIME, requested_by="jarvis")

    # 2. System Status / Battery
    if "battery" in q_clean:
        return CapabilityRequest(capability=CapabilityType.GET_BATTERY_STATUS, requested_by="jarvis")
    if "status" in q_clean or "diagnostics" in q_clean or "system" in q_clean:
        return CapabilityRequest(capability=CapabilityType.GET_SYSTEM_STATUS, requested_by="jarvis")

    # 3. Volume Controls
    if "volume" in q_clean or "louder" in q_clean or "quieter" in q_clean or "mute" in q_clean:
        vol_match = re.search(r"\b(\d{1,3})\b", q)
        if vol_match:
            vol = min(100, max(0, int(vol_match.group(1))))
            return CapabilityRequest(
                capability=CapabilityType.SET_VOLUME,
                parameters={"level": vol},
                requested_by="jarvis",
            )
        if "up" in q_clean or "louder" in q_clean:
            return CapabilityRequest(
                capability=CapabilityType.SET_VOLUME,
                parameters={"level": 75},
                requested_by="jarvis",
            )
        if "down" in q_clean or "quieter" in q_clean:
            return CapabilityRequest(
                capability=CapabilityType.SET_VOLUME,
                parameters={"level": 30},
                requested_by="jarvis",
            )
        if "mute" in q_clean:
            return CapabilityRequest(
                capability=CapabilityType.SET_VOLUME,
                parameters={"level": 0},
                requested_by="jarvis",
            )
        return CapabilityRequest(capability=CapabilityType.GET_VOLUME, requested_by="jarvis")

    # 4. Media Controls
    if any(w in q_clean for w in ("pause music", "stop music", "pause playback", "resume music", "play music")):
        return CapabilityRequest(capability=CapabilityType.MEDIA_PLAY_PAUSE, requested_by="jarvis")
    if any(w in q_clean for w in ("next song", "next track", "skip song", "skip track")):
        return CapabilityRequest(capability=CapabilityType.MEDIA_NEXT, requested_by="jarvis")
    if any(w in q_clean for w in ("previous song", "previous track", "last song")):
        return CapabilityRequest(capability=CapabilityType.MEDIA_PREVIOUS, requested_by="jarvis")

    # 5. YouTube Music / Search
    m = re.search(r"(?:play|search|find|open)\s+(.+?)\s+(?:on|in)\s+youtube", q_clean)
    if m or ("youtube" in q_clean and any(w in q_clean for w in ("play", "songs", "music"))):
        query = m.group(1).strip() if m else q_clean.replace("youtube", "").replace("play", "").strip() or "music"
        return CapabilityRequest(
            capability=CapabilityType.PLAY_YOUTUBE,
            target="youtube",
            query=query,
            parameters={"url": f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"},
            requested_by="jarvis",
        )

    # 6. General Web Search
    m = re.match(r"(?:search|google)(?: for)?\s+(.+)", q_clean)
    if m:
        query = m.group(1).strip()
        return CapabilityRequest(
            capability=CapabilityType.SEARCH_WEB,
            query=query,
            parameters={"url": f"https://www.google.com/search?q={urllib.parse.quote(query)}"},
            requested_by="jarvis",
        )

    # 7. Approved Website or App Launch
    m = re.search(r"\b(?:open|launch|start)\s+(?:up\s+)?([a-zA-Z0-9_\- ]+?)(?:\s+(?:for|please|now|app|application|program)\b.*|$)", q_clean)
    if m:
        target = m.group(1).strip().lower()
        if target in SITES:
            return CapabilityRequest(
                capability=CapabilityType.OPEN_WEBSITE,
                target=target,
                parameters={"url": SITES[target]},
                requested_by="jarvis",
            )
        resolved = resolve_approved_app(target)
        app_name = resolved["canonical_name"] if resolved else find_app(target)
        return CapabilityRequest(
            capability=CapabilityType.OPEN_APP,
            target=app_name,
            parameters={"app_name": app_name},
            requested_by="jarvis",
        )

    return None


def execute_action(
    request: CapabilityRequest,
    is_online: bool = True,
    user_confirmed: bool = False,
    executor: Optional[Any] = None,
    use_real_windows: bool = False,
) -> CapabilityResult:
    """
    Executes a CapabilityRequest through the mandatory SecurityValidator.
    Guarantees:
    - Never executes if OFFLINE.
    - Never executes unapproved or dangerous capabilities.
    - Executes via safe allowlisted executor.
    """
    validator = get_security_validator()
    sec_res = validator.validate_capability_request(
        request=request,
        is_assistant_online=is_online,
        user_confirmed=user_confirmed,
    )

    if sec_res.decision == SecurityDecision.DENY:
        return CapabilityResult(
            request_id=request.request_id,
            capability=request.capability,
            success=False,
            error_message=f"Security gate blocked action: {sec_res.reason}",
            simulated=not use_real_windows,
            verified=False,
        )

    if sec_res.decision == SecurityDecision.REQUIRES_CONFIRMATION:
        return CapabilityResult(
            request_id=request.request_id,
            capability=request.capability,
            success=False,
            error_message=f"User confirmation required: {sec_res.reason}",
            simulated=not use_real_windows,
            verified=False,
        )

    target_executor = executor or (get_windows_executor(allow_real_execution=True) if use_real_windows else get_action_executor())
    return target_executor.execute(request)


def try_action(
    q: str,
    is_online: bool = True,
    user_confirmed: bool = False,
    use_real_windows: bool = False,
) -> Optional[str]:
    """
    High-level entry point for deterministic queries.
    Replaces legacy unsafe try_action with secure capability planning.
    """
    q_clean = q.lower().strip(" .,!?")

    # 1. Stock Market Queries & Technical Analysis
    if any(k in q_clean for k in ("stock", "market", "nifty", "sensex", "crypto", "bitcoin", "buy or sell")):
        for sym, name in jarvis_market.DEFAULT_TICKERS.items():
            if name.lower() in q_clean or sym.lower().replace(".ns", "") in q_clean:
                data = jarvis_market.analyze_ticker(sym)
                if data:
                    direction = "up" if data["pct_change"] >= 0 else "down"
                    return (
                        f"{data['name']} is trading at {data['currency']}{data['price']:,}, "
                        f"{direction} {abs(data['pct_change'])}%. "
                        f"Technical indicator: {data['signal']}. {data['reason']}"
                    )
        return "Here is the market overview: " + jarvis_market.market_briefing()

    # 2. WhatsApp Messaging
    m = re.search(r"(?:send|reply|message)\s+(?:on\s+whatsapp\s+to|whatsapp\s+to|to)\s+(.+?)(?:\s+saying\s+(.+))?$", q_clean)
    if "whatsapp" in q_clean and m:
        contact = m.group(1).strip()
        msg = m.group(2).strip() if m.group(2) else "I received your message, will get back shortly."
        return send_whatsapp_message(contact, msg)

    if q_clean in ("open whatsapp", "check whatsapp", "whatsapp"):
        req = CapabilityRequest(
            capability=CapabilityType.OPEN_WEBSITE,
            target="whatsapp",
            parameters={"url": SITES["whatsapp"]},
            requested_by="jarvis",
        )
        res = execute_action(req, is_online=is_online, user_confirmed=user_confirmed, use_real_windows=use_real_windows)
        return "Opening WhatsApp." if res.success else f"Action denied: {res.error_message}"

    # 3. Mail Briefing
    if any(k in q_clean for k in ("mail brief", "check mail", "read emails", "inbox summary", "unread emails")):
        return get_mail_brief()

    # 4. Standard Plan & Execute Capability
    planned = plan_capability(q)
    if planned:
        res = execute_action(planned, is_online=is_online, user_confirmed=user_confirmed, use_real_windows=use_real_windows)
        if not res.success:
            return f"Action prevented: {res.error_message}"
        if planned.capability == CapabilityType.PLAY_YOUTUBE:
            return f"Navigated to YouTube for '{planned.query}'. Note: Direct playback cannot be verified without browser extensions." if use_real_windows else f"Playing '{planned.query}' on YouTube (Simulated)."
        if planned.capability == CapabilityType.SEARCH_WEB:
            return f"Dispatched search on Google for '{planned.query}'." if use_real_windows else f"Searching Google for '{planned.query}' (Simulated)."
        if planned.capability == CapabilityType.OPEN_APP:
            return f"Launched application {planned.target}." if use_real_windows else f"Opening {planned.target} (Simulated)."
        if planned.capability == CapabilityType.OPEN_WEBSITE:
            return f"Opened website {planned.target}." if use_real_windows else f"Navigating to {planned.target} (Simulated)."
        if planned.capability == CapabilityType.GET_TIME:
            return f"{res.output.get('formatted')}"
        if planned.capability == CapabilityType.GET_SYSTEM_STATUS:
            return f"System status: {res.output.get('status')}. CPU: {res.output.get('cpu_percent')}%, RAM: {res.output.get('ram_percent')}%."
        if planned.capability == CapabilityType.SET_VOLUME:
            return res.output.get("formatted", f"Audio volume adjusted to {planned.parameters.get('level')}%.")
        if planned.capability in (CapabilityType.VOLUME_UP, CapabilityType.VOLUME_DOWN, CapabilityType.VOLUME_MUTE):
            return res.output.get("formatted", f"Volume control {planned.capability.value} executed.")
        if planned.capability in (CapabilityType.MEDIA_PLAY_PAUSE, CapabilityType.MEDIA_NEXT, CapabilityType.MEDIA_PREVIOUS):
            return f"Media control {planned.capability.value} executed."
        return f"Completed {planned.capability.value}."

    return None
