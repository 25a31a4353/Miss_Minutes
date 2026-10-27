"""
voice/tts.py - Text-to-Speech Abstraction and Providers.

Defines the TextToSpeechProvider interface supporting:
- Gemini Speech Generation / Gemini TTS (primary candidate)
- edge-tts (multilingual fallback for English & Telugu)
- MockTTSProvider (deterministic testing)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, Field

from voice.voices import AgentVoiceProfile, get_voice_profile

logger = logging.getLogger(__name__)


class TTSAudioResult(BaseModel):
    """Audio synthesis result container."""
    audio_bytes: bytes = Field(default=b"", description="Synthesized raw or encoded audio data.")
    sample_rate: int = Field(default=24000, description="Audio sample rate in Hz.")
    voice_used: str = Field(default="", description="Identifier of the voice model utilized.")
    duration_seconds: float = Field(default=0.0, ge=0.0, description="Duration of speech in seconds.")
    text: str = Field(default="", description="Source text that was synthesized.")


class TextToSpeechProvider(ABC):
    """
    Abstract interface for Text-to-Speech synthesis engines.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Provider identifier (e.g. 'gemini-tts', 'edge-tts', 'mock')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the engine is ready and operational."""
        pass

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice_profile: Optional[AgentVoiceProfile] = None,
        language: str = "en",
    ) -> TTSAudioResult:
        """Synthesizes text into speech using the appropriate agent voice profile."""
        pass


class EdgeTTSProvider(TextToSpeechProvider):
    """
    Fallback TTS provider using Microsoft Edge TTS (`edge-tts`).
    Supports high-quality multilingual neural voices for English and Telugu.
    """

    def __init__(self):
        self._available: Optional[bool] = None

    @property
    def provider_id(self) -> str:
        return "edge-tts"

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import edge_tts  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def synthesize(
        self,
        text: str,
        voice_profile: Optional[AgentVoiceProfile] = None,
        language: str = "en",
    ) -> TTSAudioResult:
        if not self.is_available():
            raise RuntimeError("edge-tts library is not available.")

        import asyncio
        import edge_tts

        profile = voice_profile or get_voice_profile("miss_minutes")
        voice_name = profile.get_voice_for_language(language)

        async def _run_synthesis() -> bytes:
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_name,
                rate=profile.rate,
                pitch=profile.pitch,
            )
            chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            return b"".join(chunks)

        # In Phase 4, synthesis is callable in synchronous context
        try:
            audio_bytes = asyncio.run(_run_synthesis())
        except Exception as exc:
            logger.error("edge-tts synthesis failed: %s", exc)
            raise RuntimeError(f"edge-tts error: {exc}") from exc

        return TTSAudioResult(
            audio_bytes=audio_bytes,
            sample_rate=24000,
            voice_used=voice_name,
            duration_seconds=max(0.5, len(text.split()) * 0.35),
            text=text,
        )


class MockTTSProvider(TextToSpeechProvider):
    """
    Deterministic Mock TTS provider for unit testing without audio hardware or network.
    """

    def __init__(self):
        self._is_active = True
        self.synthesized_log: list[tuple[str, str]] = []

    @property
    def provider_id(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        return self._is_active

    def synthesize(
        self,
        text: str,
        voice_profile: Optional[AgentVoiceProfile] = None,
        language: str = "en",
    ) -> TTSAudioResult:
        profile = voice_profile or get_voice_profile("miss_minutes")
        voice_name = profile.get_voice_for_language(language)
        self.synthesized_log.append((text, voice_name))

        # Generate lightweight synthetic silent/dummy payload
        dummy_audio = b"RIFF" + b"\x00" * 32
        return TTSAudioResult(
            audio_bytes=dummy_audio,
            sample_rate=24000,
            voice_used=voice_name,
            duration_seconds=1.0,
            text=text,
        )
