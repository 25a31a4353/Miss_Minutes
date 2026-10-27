"""
voice/service.py - Coordinated Real Voice Interaction Service.

Coordinates:
- MicrophoneDevice (Windows microphone audio capture)
- WakeWordDetector (Local 'Hey Minutes' detection)
- SpeechToTextProvider (faster-whisper multilingual STT)
- TextToSpeechProvider (Edge-TTS / Gemini TTS)
- AudioPlayer (Speaker audio playback)

CRITICAL SAFETY CONTRACT:
Strictly enforces the OFFLINE master boundary:
If the application state is OFFLINE, all audio capture, speech transcription,
wake-word processing, and audio playback are immediately blocked and raise PermissionError.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional, Union

from voice.device import AudioDeviceManager
from voice.microphone import MicrophoneDevice
from voice.audio_player import AudioPlayer
from voice.stt import FasterWhisperSTTProvider, MockSTTProvider, SpeechToTextProvider, TranscriptionResult
from voice.tts import EdgeTTSProvider, MockTTSProvider, TTSAudioResult, TextToSpeechProvider
from voice.voices import AgentVoiceProfile, get_voice_profile
from voice.wake import AcousticWakeWordDetector, MockWakeWordDetector, WakeWordDetector, WakeWordEvent

logger = logging.getLogger(__name__)


class VoiceService:
    """
    Coordinated Voice Service for Miss Minutes + Jarvis.
    
    Guarantees:
    - Master OFFLINE gate: when assistant is OFFLINE, all audio operations are locked.
    - Synchronized voice loop: wake detection -> speech capture -> faster-whisper STT -> TTS playback.
    - Clean lifecycle without hanging threads or driver deadlocks.
    """

    def __init__(
        self,
        stt_provider: Optional[SpeechToTextProvider] = None,
        tts_provider: Optional[TextToSpeechProvider] = None,
        wake_detector: Optional[WakeWordDetector] = None,
        microphone: Optional[MicrophoneDevice] = None,
        audio_player: Optional[AudioPlayer] = None,
        is_assistant_online: bool = False,
    ):
        if stt_provider is not None:
            self._stt = stt_provider
        else:
            from voice.stt import MultilingualGoogleSTTProvider
            whisper_fb = FasterWhisperSTTProvider() if FasterWhisperSTTProvider().is_available() else MockSTTProvider()
            google_stt = MultilingualGoogleSTTProvider(fallback_provider=whisper_fb)
            self._stt = google_stt if google_stt.is_available() else whisper_fb

        self._tts = tts_provider or (
            EdgeTTSProvider() if EdgeTTSProvider().is_available() else MockTTSProvider()
        )
        self._wake = wake_detector or AcousticWakeWordDetector()
        self._mic = microphone or MicrophoneDevice()
        self._player = audio_player or AudioPlayer(is_online=is_assistant_online)
        self._online = is_assistant_online

        # Synchronize online state across sub-components
        self._mic.set_online(self._online)
        self._player.set_online(self._online)

    @property
    def is_online(self) -> bool:
        return self._online

    @property
    def microphone(self) -> MicrophoneDevice:
        return self._mic

    @property
    def audio_player(self) -> AudioPlayer:
        return self._player

    @property
    def stt_provider(self) -> SpeechToTextProvider:
        return self._stt

    @property
    def tts_provider(self) -> TextToSpeechProvider:
        return self._tts

    @property
    def wake_detector(self) -> WakeWordDetector:
        return self._wake

    def set_online(self, online: bool) -> None:
        """Sets the master online status across all voice components."""
        self._online = online
        self._mic.set_online(online)
        self._player.set_online(online)

        if not online and self._wake.is_enabled():
            self._wake.stop()

    def start_wake_detection(self, callback: Optional[Callable[[WakeWordEvent], None]] = None) -> None:
        """Starts wake-word detection only if assistant is online."""
        if not self._online:
            raise PermissionError("Assistant is OFFLINE: Wake-word detection is strictly blocked.")
        self._wake.start(callback=callback)

    def stop_wake_detection(self) -> None:
        """Stops wake-word detection."""
        self._wake.stop()

    def capture_speech(self, timeout_seconds: float = 4.0) -> bytes:
        """Captures an audio phrase from the microphone."""
        if not self._online:
            raise PermissionError("Assistant is OFFLINE: Speech capture is strictly blocked.")
        return self._mic.capture_phrase(timeout_seconds=timeout_seconds)

    def transcribe_audio(
        self,
        audio_data: Union[bytes, Path, str],
        language_hint: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribes audio data using the multilingual STT engine."""
        if not self._online:
            raise PermissionError("Assistant is OFFLINE: Audio transcription is strictly blocked.")
        return self._stt.transcribe(audio_data, language_hint=language_hint)

    def speak_text(
        self,
        text: str,
        agent_name: str = "miss_minutes",
        language: str = "en",
        play_audio: bool = True,
    ) -> TTSAudioResult:
        """
        Synthesizes text using the designated agent's distinct voice profile
        and optionally plays the synthesized speech through the system speakers.
        """
        if not self._online:
            raise PermissionError("Assistant is OFFLINE: Speech synthesis is strictly blocked.")

        profile = get_voice_profile(agent_name)
        tts_result = self._tts.synthesize(text, voice_profile=profile, language=language)

        # Output audio playback to speaker if enabled and audio is present
        if play_audio and tts_result.audio_bytes:
            try:
                self._player.play_bytes(tts_result.audio_bytes, format_hint="mp3", blocking=False)
            except Exception as exc:
                logger.warning("Speaker playback error: %s", exc)

        return tts_result

    def speak_text_blocking(
        self,
        text: str,
        agent_name: str = "miss_minutes",
        language: str = "te",
    ) -> TTSAudioResult:
        """
        Synthesizes and plays audio, waiting synchronously until playback finishes.
        Guarantees that sequential speakers do not talk over each other.
        """
        if not self._online:
            raise PermissionError("Assistant is OFFLINE: Speech synthesis is strictly blocked.")

        profile = get_voice_profile(agent_name)
        tts_result = self._tts.synthesize(text, voice_profile=profile, language=language)

        if tts_result.audio_bytes:
            try:
                self._player.play_bytes(tts_result.audio_bytes, format_hint="mp3", blocking=True)
            except Exception as exc:
                logger.warning("Speaker playback error: %s", exc)

        return tts_result

    def speak_turn_taking(
        self,
        miss_minutes_text: str,
        jarvis_text: str,
        language: str = "te",
    ) -> None:
        """
        Executes turn-taking dialogue between Miss Minutes and Jarvis:
        1. Miss Minutes speaks first.
        2. Waits until her speech finishes.
        3. Jarvis speaks second.
        Guarantees: they NEVER speak at the same time!
        """
        import time
        if miss_minutes_text and miss_minutes_text.strip():
            self.speak_text_blocking(miss_minutes_text.strip(), agent_name="miss_minutes", language=language)
            time.sleep(0.25)

        if jarvis_text and jarvis_text.strip():
            self.speak_text_blocking(jarvis_text.strip(), agent_name="jarvis", language=language)

    def process_voice_interaction(
        self,
        timeout_seconds: float = 4.0,
        language_hint: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Executes a single voice input session:
        Microphone capture -> faster-whisper transcription.
        """
        if not self._online:
            raise PermissionError("Assistant is OFFLINE: Voice interaction is strictly blocked.")

        raw_wav = self.capture_speech(timeout_seconds=timeout_seconds)
        return self.transcribe_audio(raw_wav, language_hint=language_hint)
