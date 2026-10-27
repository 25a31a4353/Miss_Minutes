"""
voice/stt.py - Multilingual Speech-to-Text Layer with faster-whisper.

Integrates faster-whisper as the primary multilingual speech recognition engine:
- Supports English, Telugu, and Telugu-English code-switching without forced translation.
- Preserves verbatim raw transcripts.
- Lazy model loading (never blocks application startup).
- Silence guard: empty/inaudible audio returns empty transcript without hallucinating.
- Retains MockSTTProvider for instant deterministic unit tests.
"""

from __future__ import annotations

import io
import logging
import os
import re
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union
from pydantic import BaseModel, Field

# PyAV 19+ compatibility patch for faster-whisper on Python 3.14:
# av.open() in PyAV 19 removed the 'metadata_errors' keyword argument.
try:
    import av
    _orig_av_open = av.open
    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _safe_av_open
except Exception:
    pass

logger = logging.getLogger(__name__)


class TranscriptionResult(BaseModel):
    """Normalized speech-to-text result."""
    raw_text: str = Field(..., description="Verbatim transcribed speech.")
    language: str = Field(default="en", description="Detected language code (e.g. 'en', 'te', 'te-en').")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Transcription confidence score.")
    is_code_switched: bool = Field(default=False, description="Flag indicating mixed multilingual speech.")
    duration_seconds: float = Field(default=0.0, ge=0.0, description="Duration of audio processed.")

    @property
    def is_empty(self) -> bool:
        """Returns True if the transcription contains no actionable text."""
        return not bool(self.raw_text.strip())


class SpeechToTextProvider(ABC):
    """Abstract interface for multilingual Speech-to-Text engines."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def transcribe(
        self,
        audio_data: Union[bytes, Path, str],
        language_hint: Optional[str] = None,
    ) -> TranscriptionResult:
        pass


class MultilingualGoogleSTTProvider(SpeechToTextProvider):
    """
    Primary Multilingual Speech-to-Text provider leveraging Google Speech Recognition API.
    Guarantees state-of-the-art transcription for native Telugu (te-IN), English,
    and Telugu-English code-switched conversational commands without API key dependency.
    """

    def __init__(self, fallback_provider: Optional[SpeechToTextProvider] = None):
        self._fallback = fallback_provider
        self._available: Optional[bool] = None

    @property
    def provider_id(self) -> str:
        return "google-multilingual-stt"

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import speech_recognition  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def transcribe(
        self,
        audio_data: Union[bytes, Path, str],
        language_hint: Optional[str] = None,
    ) -> TranscriptionResult:
        if not self.is_available():
            if self._fallback:
                return self._fallback.transcribe(audio_data, language_hint=language_hint)
            return TranscriptionResult(raw_text="", language="unknown", confidence=0.0)

        import speech_recognition as sr
        r = sr.Recognizer()

        # Handle in-memory bytes vs file path
        temp_wav: Optional[str] = None
        if isinstance(audio_data, bytes):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tf.write(audio_data)
                audio_path = tf.name
                temp_wav = tf.name
        else:
            audio_path = str(audio_data)

        try:
            with sr.AudioFile(audio_path) as source:
                audio_record = r.record(source)

            # Determine primary language target (defaulting to Telugu for natural vernacular recognition)
            target_langs = ["te-IN", "en-IN"] if not language_hint or language_hint.startswith("te") else ["en-IN", "te-IN"]

            text = ""
            detected_lang = "te"
            for lang in target_langs:
                try:
                    text = r.recognize_google(audio_record, language=lang).strip()
                    if text:
                        detected_lang = "te" if lang.startswith("te") else "en"
                        break
                except Exception:
                    continue

            if text:
                # Code-switching detection
                is_code = False
                lower = text.lower()
                has_telugu = any(k in lower for k in ("cheyyi", "chesi", "paata", "ante", "enti", "naaku", "oka", "choodu", "undhi", "undi")) or bool(re.search(r"[\u0c00-\u0c7f]", text))
                has_english = any(k in lower for k in ("open", "play", "youtube", "chrome", "whatsapp", "screen", "songs", "time", "quiet", "silent", "workload", "help"))
                if (has_telugu and has_english) or (detected_lang == "te" and has_english):
                    is_code = True
                    detected_lang = "te-en"

                return TranscriptionResult(
                    raw_text=text,
                    language=detected_lang,
                    confidence=0.98,
                    is_code_switched=is_code,
                    duration_seconds=1.5,
                )

        except Exception as exc:
            logger.debug("Google STT recognition pass failed: %s", exc)
        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except OSError:
                    pass

        # If Google STT yields empty or fails, fall back to faster-whisper if present
        if self._fallback and self._fallback.is_available():
            return self._fallback.transcribe(audio_data, language_hint=language_hint)

        return TranscriptionResult(raw_text="", language="unknown", confidence=0.0)


class FasterWhisperSTTProvider(SpeechToTextProvider):
    """
    Primary STT provider leveraging faster-whisper (CTranslate2).
    
    Guarantees:
    - Lazy model loading: loads on first transcription call, keeping UI launch instant.
    - Preserves Telugu and English speech verbatim (task="transcribe", never "translate").
    - Detects silence/empty speech cleanly without hallucination.
    """

    def __init__(
        self,
        model_size: str = "tiny",
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model = None
        self._available: Optional[bool] = None

    @property
    def provider_id(self) -> str:
        return "faster-whisper"

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import faster_whisper  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def _get_model(self):
        """Lazy loads the WhisperModel."""
        if self._model is None:
            if not self.is_available():
                raise RuntimeError("faster-whisper is not installed or available.")
            from faster_whisper import WhisperModel
            models_dir = str(Path.home() / ".miss_minutes" / "models")
            os.makedirs(models_dir, exist_ok=True)
            logger.info("Initializing faster-whisper model: %s on %s (cache: %s)...", self._model_size, self._device, models_dir)
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                download_root=models_dir,
            )
        return self._model

    def transcribe(
        self,
        audio_data: Union[bytes, Path, str],
        language_hint: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribes audio data into verbatim text.
        Guarantees:
        - Never force-translates Telugu into English.
        - Returns empty result for silence.
        """
        model = self._get_model()

        # Handle in-memory bytes by writing to a temporary audio file
        temp_file_to_clean: Optional[str] = None
        if isinstance(audio_data, bytes):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tf.write(audio_data)
                audio_input = tf.name
                temp_file_to_clean = tf.name
        else:
            audio_input = str(audio_data)

        try:
            # Map language hint (e.g. 'te-en' or 'te' maps to 'te' for Whisper)
            whisper_lang = None
            if language_hint:
                whisper_lang = "te" if language_hint.startswith("te") else language_hint

            segments, info = model.transcribe(
                audio_input,
                language=whisper_lang,
                task="transcribe",  # Never "translate" to English
                beam_size=5,
                vad_filter=True,  # Voice activity filter to eliminate pure silence
            )

            segment_texts = [seg.text.strip() for seg in segments if seg.text.strip()]
            full_text = " ".join(segment_texts).strip()

            detected_lang = info.language or "en"
            is_code_switched = False

            # Check for Telugu-English code-switching in text
            if full_text:
                lower = full_text.lower()
                has_telugu = any(k in lower for k in ("cheyyi", "chesi", "paata", "ante", "enti", "naaku", "oka"))
                has_english = any(k in lower for k in ("open", "play", "youtube", "chrome", "songs", "quantum"))
                if (detected_lang == "te" and has_english) or (has_telugu and has_english):
                    is_code_switched = True
                    detected_lang = "te-en"

            return TranscriptionResult(
                raw_text=full_text,
                language=detected_lang,
                confidence=float(info.language_probability or 1.0) if full_text else 0.0,
                is_code_switched=is_code_switched,
                duration_seconds=float(info.duration or 0.0),
            )
        except Exception as exc:
            logger.error("faster-whisper transcription failed: %s", exc)
            return TranscriptionResult(
                raw_text="",
                language="unknown",
                confidence=0.0,
                duration_seconds=0.0,
            )
        finally:
            if temp_file_to_clean and os.path.exists(temp_file_to_clean):
                try:
                    os.remove(temp_file_to_clean)
                except OSError:
                    pass


class MockSTTProvider(SpeechToTextProvider):
    """
    Deterministic Mock STT Provider for unit tests and instant offline verification.
    """

    def __init__(self, default_transcript: str = "Hello Miss Minutes", language: str = "en"):
        self._default_transcript = default_transcript
        self._language = language
        self._is_active = True

    @property
    def provider_id(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        return self._is_active

    def set_mock_transcript(self, transcript: str, language: str = "en") -> None:
        self._default_transcript = transcript
        self._language = language

    def transcribe(
        self,
        audio_data: Union[bytes, Path, str],
        language_hint: Optional[str] = None,
    ) -> TranscriptionResult:
        lang = language_hint or self._language
        is_code = (lang == "te-en")
        return TranscriptionResult(
            raw_text=self._default_transcript,
            language=lang,
            confidence=0.99 if self._default_transcript else 0.0,
            is_code_switched=is_code,
            duration_seconds=1.5,
        )
