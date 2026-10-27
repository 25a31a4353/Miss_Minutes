"""
actions/apps.py - Allowlisted Applications and Safe URL Definitions for Phase 7.

Maintains the explicit Windows application allowlist and domain allowlist.
Arbitrary executable paths, shell scripts, and unlisted binaries are strictly prohibited.
"""

from __future__ import annotations

import ipaddress
import os
import re
import urllib.parse
from typing import Any, Optional

# Curated dictionary of approved desktop applications
APPROVED_APPLICATIONS: dict[str, dict[str, Any]] = {
    "notepad": {
        "canonical_name": "Notepad",
        "executable": "notepad.exe",
        "description": "Windows text editor",
        "fallback_paths": [
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "notepad.exe"),
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "notepad.exe"),
        ],
    },
    "calculator": {
        "canonical_name": "Calculator",
        "executable": "calc.exe",
        "description": "Windows calculator",
        "fallback_paths": [
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "calc.exe"),
        ],
    },
    "explorer": {
        "canonical_name": "File Explorer",
        "executable": "explorer.exe",
        "description": "Windows file explorer",
        "fallback_paths": [
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "explorer.exe"),
        ],
    },
    "browser": {
        "canonical_name": "Default Web Browser",
        "executable": "msedge.exe",
        "description": "Web browser",
        "fallback_paths": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
    },
    "edge": {
        "canonical_name": "Microsoft Edge",
        "executable": "msedge.exe",
        "description": "Microsoft Edge browser",
        "fallback_paths": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
    },
    "chrome": {
        "canonical_name": "Google Chrome",
        "executable": "chrome.exe",
        "description": "Google Chrome browser",
        "fallback_paths": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
    },
    "terminal": {
        "canonical_name": "Windows Terminal",
        "executable": "wt.exe",
        "description": "Windows Terminal",
        "fallback_paths": [],
    },
    "taskmgr": {
        "canonical_name": "Task Manager",
        "executable": "taskmgr.exe",
        "description": "Windows task manager",
        "fallback_paths": [
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskmgr.exe"),
        ],
    },
    "code": {
        "canonical_name": "Visual Studio Code",
        "executable": "Code.exe",
        "description": "Visual Studio Code editor",
        "fallback_paths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ],
    },
    "settings": {
        "canonical_name": "Windows Settings",
        "executable": "ms-settings:",
        "description": "Windows system settings",
        "is_protocol": True,
        "fallback_paths": [],
    },
    "whatsapp": {
        "canonical_name": "WhatsApp",
        "executable": "whatsapp:",
        "description": "WhatsApp Desktop or Web",
        "is_protocol": True,
        "fallback_paths": [
            os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
            os.path.expandvars(r"%ProgramFiles%\WindowsApps\WhatsApp.exe"),
            r"C:\Program Files\WindowsApps\WhatsApp.exe",
        ],
        "web_fallback": "https://web.whatsapp.com",
    },
}

# User query alias mappings to canonical app keys
APPLICATION_ALIASES: dict[str, str] = {
    "notepad": "notepad",
    "note": "notepad",
    "text editor": "notepad",
    "calculator": "calculator",
    "calc": "calculator",
    "explorer": "explorer",
    "file explorer": "explorer",
    "files": "explorer",
    "my computer": "explorer",
    "browser": "browser",
    "web browser": "browser",
    "internet": "browser",
    "edge": "edge",
    "ms edge": "edge",
    "microsoft edge": "edge",
    "chrome": "chrome",
    "google chrome": "chrome",
    "terminal": "terminal",
    "windows terminal": "terminal",
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",
    "code": "code",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "settings": "settings",
    "windows settings": "settings",
    "whatsapp": "whatsapp",
    "whats app": "whatsapp",
    "wa": "whatsapp",
    "whatsapp web": "whatsapp",
}

# Approved web domains for OPEN_WEBSITE capability
APPROVED_DOMAINS: set[str] = {
    "youtube.com",
    "www.youtube.com",
    "google.com",
    "www.google.com",
    "github.com",
    "www.github.com",
    "wikipedia.org",
    "en.wikipedia.org",
    "maps.google.com",
    "mail.google.com",
    "calendar.google.com",
    "drive.google.com",
    "web.whatsapp.com",
    "whatsapp.com",
    "www.whatsapp.com",
}


def resolve_approved_app(app_query: str | None) -> Optional[dict[str, Any]]:
    """
    Resolves an application name/alias to an approved application descriptor.
    Returns None if the application is not approved.
    Strictly forbids arbitrary file paths or dynamic command strings.
    """
    if not app_query:
        return None

    clean = app_query.strip().lower()

    # Reject path traversal, explicit paths, and shell injection characters
    if any(sep in clean for sep in ("/", "\\", ":", "..", "&", "|", ";", "`", "$", "<", ">", "%", "\n", "\r")):
        return None

    # Check direct canonical key
    if clean in APPROVED_APPLICATIONS:
        return APPROVED_APPLICATIONS[clean]

    # Check alias dictionary
    if clean in APPLICATION_ALIASES:
        key = APPLICATION_ALIASES[clean]
        return APPROVED_APPLICATIONS.get(key)

    # Whole word / boundary search in known aliases
    for alias_key, target_key in APPLICATION_ALIASES.items():
        if alias_key == clean:
            return APPROVED_APPLICATIONS.get(target_key)
        if len(alias_key) >= 4 and alias_key in clean:
            return APPROVED_APPLICATIONS.get(target_key)
        if re.search(rf"\b{re.escape(alias_key)}\b", clean):
            return APPROVED_APPLICATIONS.get(target_key)

    return None


def is_app_approved(app_query: str | None) -> bool:
    """Checks whether the application query maps to an approved application."""
    return resolve_approved_app(app_query) is not None


def is_safe_url(url_str: str | None) -> tuple[bool, str]:
    """
    Validates a URL against strict security requirements:
    1. Must parse cleanly.
    2. Scheme must be strictly http or https (no file://, data:, javascript:).
    3. Hostname must be present and not point to private/loopback/link-local IP addresses.
    4. Hostname must match the approved domain allowlist.
    Returns (is_safe, error_reason).
    """
    if not url_str or not url_str.strip():
        return False, "URL string is empty."

    clean_url = url_str.strip()

    # Prohibit control characters or newlines
    if re.search(r"[\r\n\x00-\x1f]", clean_url):
        return False, "URL contains illegal control characters."

    try:
        parsed = urllib.parse.urlparse(clean_url)
    except Exception as exc:
        return False, f"URL parsing error: {exc}"

    # 1. Scheme check
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Unsafe URL scheme '{parsed.scheme}': only http and https are permitted."

    # 2. Hostname check
    host = parsed.hostname
    if not host:
        return False, "URL missing valid hostname."

    host_lower = host.lower()

    # Prohibit localhost and common loopback names
    if host_lower in ("localhost", "0.0.0.0", "127.0.0.1", "::1"):
        return False, f"Access to localhost/loopback address '{host}' is prohibited."

    # Check for private or loopback IP addresses
    try:
        ip = ipaddress.ip_address(host_lower)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            return False, f"Access to private/local IP address '{host}' is prohibited."
    except ValueError:
        # Not an IP address string, host is a domain name
        pass

    # 3. Domain allowlist check
    def matches_approved_domain(h: str) -> bool:
        for approved in APPROVED_DOMAINS:
            if h == approved or h.endswith("." + approved):
                return True
        return False

    if not matches_approved_domain(host_lower):
        return False, f"Domain '{host_lower}' is not in the approved URL allowlist."

    return True, ""
