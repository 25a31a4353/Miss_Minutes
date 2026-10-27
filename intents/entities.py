"""
intents/entities.py - Entity Definitions and Canonical Mappings.

Provides allowlisted alias mappings for:
- Desktop application names
- Approved website domains
- Safe command entity extraction
"""

from __future__ import annotations

# Canonical application alias map
APPLICATION_ALIASES: dict[str, str] = {
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "notepad": "Notepad",
    "calculator": "Calculator",
    "calc": "Calculator",
    "explorer": "File Explorer",
    "files": "File Explorer",
    "terminal": "Windows Terminal",
    "code": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "spotify": "Spotify",
    "browser": "Default Web Browser",
    "edge": "Microsoft Edge",
    "taskmgr": "Task Manager",
    "task manager": "Task Manager",
    "settings": "Windows Settings",
    "whatsapp": "WhatsApp",
    "whats app": "WhatsApp",
    "wa": "WhatsApp",
}

# Canonical website aliases
WEBSITE_ALIASES: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
    "wikipedia": "https://www.wikipedia.org",
    "reddit": "https://www.reddit.com",
    "news": "https://news.google.com",
    "whatsapp": "https://web.whatsapp.com",
}


def normalize_app_name(raw_name: str | None) -> str | None:
    """Returns canonical app name if recognized, or cleaned raw name."""
    if not raw_name:
        return None
    key = raw_name.strip().lower()
    return APPLICATION_ALIASES.get(key, raw_name.strip())


def normalize_website_url(raw_target: str | None) -> str | None:
    """Returns canonical URL for recognized web targets."""
    if not raw_target:
        return None
    key = raw_target.strip().lower()
    if key in WEBSITE_ALIASES:
        return WEBSITE_ALIASES[key]
    if key.startswith("http://") or key.startswith("https://"):
        return key
    return f"https://www.{key}.com"
