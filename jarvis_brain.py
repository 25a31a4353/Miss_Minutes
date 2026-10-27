"""
jarvis_brain.py - Jarvis AI Brain (Gemini Primary, Groq Fallback, Security Integrated).

EVOLUTION & REFACTORING:
- Upgraded to use AIProvider abstraction (Google Gemini primary via google-genai, Groq fallback).
- Preserves Jarvis's calm, technically precise, dry-witted personality and concise delivery.
- Preserves rate limit detection, cooldown failover, and local capability fallbacks.
- Fully supports Telugu, English, and code-switched technical inquiries.
- Integrates seamlessly with jarvis_actions.py for security-validated capability planning.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import jarvis_actions
from ai.provider import AIProvider, ModelConfig, ProviderResponse
from ai.gemini_provider import GeminiProvider
from ai.groq_provider import GroqProvider
from ai.mock_provider import MockAIProvider
from ai.prompts import JARVIS_SYSTEM_PROMPT
from actions.schemas import CapabilityRequest

logger = logging.getLogger(__name__)

KEYFILE = os.path.expanduser("~/.openjarvis/free.key")
DEFAULT_GROQ_MODELS = ["llama-3.3-70b-versatile"]

_provider: Optional[AIProvider] = None
_history: List[Dict[str, str]] = []
_cooldown_until: float = 0.0

# Jarvis persona prompt preserved and refined
SYSTEM_PROMPT = JARVIS_SYSTEM_PROMPT


from ai.fallback_provider import ResilientAIProvider


def _get_api_key() -> Optional[str]:
    """Retrieves API key from environment or local keyfile."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"].strip()
    if os.environ.get("GROQ_API_KEY"):
        return os.environ["GROQ_API_KEY"].strip()
    if os.path.exists(KEYFILE):
        try:
            return open(KEYFILE).read().strip()
        except OSError:
            pass
    return None


def get_ai_provider() -> AIProvider:
    """Returns the active AI provider, using ResilientAIProvider (Gemini -> Groq -> Mock)."""
    global _provider
    if _provider is not None:
        return _provider

    primary: Optional[AIProvider] = None
    gemini_key = os.environ.get("GEMINI_API_KEY")
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    if gemini_key and gemini_key.strip():
        primary = GeminiProvider(api_key=gemini_key.strip(), default_model=gemini_model)

    secondary: Optional[AIProvider] = None
    groq_key = os.environ.get("GROQ_API_KEY") or _get_api_key()
    if groq_key and groq_key.strip():
        secondary = GroqProvider(api_key=groq_key.strip())

    from ai.free_intelligence import FreeIntelligenceProvider

    tertiary = FreeIntelligenceProvider()

    fallback = MockAIProvider(
        default_text_response="All parameters verified, sir. Standing by for your instructions."
    )

    _provider = ResilientAIProvider(
        primary=primary,
        secondary=secondary,
        tertiary=tertiary,
        fallback=fallback,
    )
    return _provider


def set_ai_provider(provider: AIProvider) -> None:
    """Explicitly injects an AI provider (e.g. for testing)."""
    global _provider
    _provider = provider


def ready() -> bool:
    """Returns True if the cloud brain is active and not in cooldown."""
    return time.time() >= _cooldown_until


def _set_cooldown(secs: float) -> None:
    global _cooldown_until
    _cooldown_until = max(_cooldown_until, time.time() + float(secs))


def _local_fallback(q: str, is_online: bool = True) -> str:
    """
    Called when cloud AI is rate-limited or unconfigured.
    Provides immediate local action execution or cached briefing without crashing.
    """
    action_res = jarvis_actions.try_action(q, is_online=is_online)
    if action_res:
        return action_res

    return (
        "Cloud API is offline or cooling down, sir, but local system diagnostics are fully active. "
        "I can launch applications, provide market summaries, or prepare media streams."
    )


def plan_capability(q: str) -> Optional[CapabilityRequest]:
    """Delegates to jarvis_actions to generate a typed CapabilityRequest."""
    return jarvis_actions.plan_capability(q)


def think(q: str, is_online: bool = True, context: Optional[Any] = None) -> str:
    """
    Main reasoning entry point for queries.
    Tries local actions first, then AI provider, with automatic fallback if rate-limited.
    """
    global _history

    # 1. Master OFFLINE Gate
    if not is_online:
        return "Assistant is OFFLINE, sir. Systems are locked and standing down."

    # 2. Immediate deterministic action check
    local_done = jarvis_actions.try_action(q, is_online=is_online)
    if local_done:
        return local_done

    if time.time() < _cooldown_until:
        return _local_fallback(q, is_online=is_online)

    provider = get_ai_provider()
    if not provider.is_available():
        return _local_fallback(q, is_online=is_online)

    cfg = ModelConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.5,
        max_tokens=350,
    )

    history_msgs = list(_history)
    history_msgs.append({"role": "user", "content": q})

    try:
        resp = provider.generate_chat_response(history_msgs, config=cfg)
        answer = resp.content.strip()
        _history.append({"role": "user", "content": q})
        _history.append({"role": "assistant", "content": answer})
        max_turns = int(os.environ.get("MAX_CONVERSATION_TURNS", "10"))
        if len(_history) > max_turns * 2:
            _history = _history[-(max_turns * 2):]
        return answer
    except Exception as exc:
        err_msg = str(exc).lower()
        if any(w in err_msg for w in ("429", "rate limit", "quota", "too many requests")):
            _set_cooldown(60.0)
            logger.warning("Rate-limit triggered on AI provider, cooling down for 60s: %s", exc)
        else:
            logger.error("AI provider reasoning failed: %s", exc)
        return _local_fallback(q, is_online=is_online)
