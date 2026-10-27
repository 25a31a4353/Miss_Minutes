"""
tests/test_settings.py - Configuration Layer Unit Tests.

Verifies:
- Settings load safely when .env is absent.
- Missing API keys do not crash the application.
- Provider detection logic works accurately.
- Environment variables cleanly override defaults.
"""

from pathlib import Path
import tempfile
import pytest

from config.settings import AppSettings, load_settings


def test_default_settings_without_env_file() -> None:
    """Verifies default settings are returned when no .env exists."""
    non_existent = Path("non_existent_env_file_12345.env")
    settings = load_settings(env_path=non_existent)

    assert settings.app_name == "Miss Minutes"
    assert settings.default_provider == "gemini"
    assert settings.gemini_api_key is None
    assert settings.groq_api_key is None
    assert settings.start_state == "OFFLINE"
    assert settings.always_on_top is True
    assert settings.has_gemini is False
    assert settings.has_groq is False
    assert settings.has_any_provider is False


def test_provider_configured_checks() -> None:
    """Verifies is_provider_configured for both gemini and groq."""
    settings_empty = AppSettings()
    assert settings_empty.is_provider_configured("gemini") is False
    assert settings_empty.is_provider_configured("groq") is False
    assert settings_empty.is_provider_configured("unknown") is False

    settings_with_gemini = AppSettings(gemini_api_key="test_key_gemini")
    assert settings_with_gemini.is_provider_configured("gemini") is True
    assert settings_with_gemini.is_provider_configured("groq") is False
    assert settings_with_gemini.has_any_provider is True

    settings_with_groq = AppSettings(groq_api_key="test_key_groq")
    assert settings_with_groq.is_provider_configured("gemini") is False
    assert settings_with_groq.is_provider_configured("groq") is True
    assert settings_with_groq.has_any_provider is True


def test_custom_env_file_parsing() -> None:
    """Verifies that .env file parsing works properly without third-party dependencies."""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env", encoding="utf-8") as f:
        f.write("# Sample configuration\n")
        f.write("APP_NAME=Custom Minutes\n")
        f.write("AI_DEFAULT_PROVIDER=groq\n")
        f.write("GEMINI_API_KEY=test_gemini_val\n")
        f.write("APP_ALWAYS_ON_TOP=false\n")
        f.write("APP_START_STATE=IDLE\n")
        temp_path = f.name

    try:
        settings = load_settings(env_path=temp_path)
        assert settings.app_name == "Custom Minutes"
        assert settings.default_provider == "groq"
        assert settings.gemini_api_key == "test_gemini_val"
        assert settings.always_on_top is False
        assert settings.start_state == "IDLE"
        assert settings.has_gemini is True
    finally:
        Path(temp_path).unlink(missing_ok=True)
