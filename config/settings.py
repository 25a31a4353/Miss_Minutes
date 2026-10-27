"""
config/settings.py - Safe Configuration Layer for Miss Minutes.

Guarantees:
- Safe startup with zero configuration / missing API keys.
- Reads .env file if present, but never crashes if missing.
- Reads OS environment variables with sensible defaults.
- Never commits or stores secrets in plain source code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _parse_float(value: Optional[str], default: float = 1.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _parse_int(value: Optional[str], default: int = 10) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class AppSettings:
    """Immutable application settings container."""

    app_name: str = "Miss Minutes"
    default_provider: str = "gemini"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    max_conversation_turns: int = 10
    groq_api_key: Optional[str] = None
    always_on_top: bool = True
    overlay_opacity: float = 0.98
    start_state: str = "OFFLINE"
    log_level: str = "INFO"
    data_dir: Path = field(default_factory=lambda: Path.home() / ".miss_minutes")

    @property
    def has_gemini(self) -> bool:
        """Returns True if a non-empty Gemini API key is configured."""
        return bool(self.gemini_api_key and self.gemini_api_key.strip())

    @property
    def has_groq(self) -> bool:
        """Returns True if a non-empty Groq API key is configured."""
        return bool(self.groq_api_key and self.groq_api_key.strip())

    @property
    def has_any_provider(self) -> bool:
        """Returns True if at least one AI provider is configured."""
        return self.has_gemini or self.has_groq

    def is_provider_configured(self, provider_id: str) -> bool:
        """Checks if the requested provider ID has valid configuration."""
        pid = provider_id.strip().lower()
        if pid == "gemini":
            return self.has_gemini
        if pid == "groq":
            return self.has_groq
        return False


def load_settings(env_path: Optional[Path | str] = None) -> AppSettings:
    """
    Loads application settings from an optional .env file and environment variables.
    
    If the specified .env file does not exist, safe defaults are returned.
    This guarantees the application will never crash on missing configuration.
    """
    # 1. Parse .env files if present (custom simple parser to avoid external dependencies)
    env_vars: dict[str, str] = {}
    
    candidate_paths: list[Path] = []
    if env_path:
        candidate_paths.append(Path(env_path))
    else:
        # Check standard locations: local .env and per-user config.env
        candidate_paths.append(Path(".env"))
        user_config_env = Path.home() / ".miss_minutes" / "config.env"
        if user_config_env.is_file():
            candidate_paths.append(user_config_env)

    for target_env in candidate_paths:
        if target_env.is_file():
            try:
                with open(target_env, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key and key not in env_vars:
                            env_vars[key] = val
            except OSError:
                # File read error: fail closed to safe defaults without crashing
                pass

    def get_val(key: str, default: str) -> str:
        # OS environment variable takes precedence over .env file
        return os.environ.get(key, env_vars.get(key, default))

    def get_opt_val(key: str) -> Optional[str]:
        val = os.environ.get(key, env_vars.get(key, ""))
        return val.strip() if val.strip() else None

    # Custom or home data directory
    data_dir_str = get_val("APP_DATA_DIR", "")
    data_dir = Path(data_dir_str) if data_dir_str else Path.home() / ".miss_minutes"

    return AppSettings(
        app_name=get_val("APP_NAME", "Miss Minutes"),
        default_provider=get_val("AI_DEFAULT_PROVIDER", "gemini").lower(),
        gemini_api_key=get_opt_val("GEMINI_API_KEY"),
        gemini_model=get_val("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        max_conversation_turns=_parse_int(get_val("MAX_CONVERSATION_TURNS", "10"), default=10),
        groq_api_key=get_opt_val("GROQ_API_KEY"),
        always_on_top=_parse_bool(get_val("APP_ALWAYS_ON_TOP", "true"), default=True),
        overlay_opacity=_parse_float(get_val("APP_OVERLAY_OPACITY", "0.98"), default=0.98),
        start_state=get_val("APP_START_STATE", "OFFLINE").upper(),
        log_level=get_val("LOG_LEVEL", "INFO").upper(),
        data_dir=data_dir,
    )
