"""
jarvis_voice.py - Jarvis Audio & Speech Interface (Shared Voice Integration).

EVOLUTION & REFACTORING:
- Removed macOS say command and blocking infinite microphone loop.
- Integrated with shared voice/ infrastructure and Jarvis's distinct voice profile
  (en-GB-RyanNeural / te-IN-MohanNeural).
- Respects the master OFFLINE gate.
"""

from __future__ import annotations

import logging
from typing import Optional

import jarvis_brain
from voice.voices import get_voice_profile, JARVIS_VOICE_PROFILE
from voice.tts import TextToSpeechProvider, MockTTSProvider, TTSAudioResult
from voice.service import VoiceService

logger = logging.getLogger(__name__)

_voice_service: Optional[VoiceService] = None


def get_voice_service() -> VoiceService:
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService(is_assistant_online=True)
    return _voice_service


def set_voice_service(service: VoiceService) -> None:
    global _voice_service
    _voice_service = service


def speak(text: str, language: str = "en", is_online: bool = True) -> Optional[TTSAudioResult]:
    """
    Speaks output aloud using Jarvis's distinct voice profile.
    Guarantees:
    - Never executes if assistant is OFFLINE.
    - Uses Jarvis's British/formal voice profile (en-GB-RyanNeural / te-IN-MohanNeural).
    """
    if not text:
        return None

    if not is_online:
        logger.info("Jarvis audio synthesis blocked: Assistant is OFFLINE.")
        return None

    svc = get_voice_service()
    svc.set_online(is_online)
    try:
        return svc.speak_text(text, agent_name="jarvis", language=language)
    except Exception as exc:
        logger.warning("Jarvis speech synthesis warning: %s", exc)
        return None
