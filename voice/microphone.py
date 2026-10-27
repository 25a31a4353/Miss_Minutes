"""
voice/microphone.py - Windows Microphone Audio Capture Layer.

Provides explicit microphone device handling for Miss Minutes:
- Windows compatible with PySide6.QtMultimedia or fallback audio buffer.
- Clean start/stop lifecycle with timeout guards (no infinite blocking loops).
- Master OFFLINE Gate: Microphone is strictly blocked and disabled when assistant is OFFLINE.
- Test injection interface for automated deterministic test suites.
"""

from __future__ import annotations

import io
import logging
import threading
import time
import wave
from typing import Callable, Optional

from voice.device import AudioDeviceManager, AudioDeviceInfo

logger = logging.getLogger(__name__)


def create_wav_bytes(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wraps raw 16-bit PCM data into a valid WAV container in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


class MicrophoneDevice:
    """
    Windows-compatible microphone capture device.
    
    Guarantees:
    - Strictly obeys the OFFLINE state: all capture immediately stops or is refused if offline.
    - Timeout-guarded phrase capture: never blocks indefinitely.
    - Gracefully handles missing microphone hardware or driver errors.
    - Supports mock/injected audio for automated deterministic tests.
    """

    def __init__(
        self,
        device_manager: Optional[AudioDeviceManager] = None,
        sample_rate: int = 16000,
        channels: int = 1,
    ):
        self._device_mgr = device_manager or AudioDeviceManager()
        self._sample_rate = sample_rate
        self._channels = channels
        self._is_capturing = False
        self._online = False
        self._injected_audio: Optional[bytes] = None
        self._audio_source = None
        self._io_device = None

    @property
    def is_online(self) -> bool:
        return self._online

    def set_online(self, online: bool) -> None:
        """Sets the master online status. If set to False, immediately stops active capture."""
        self._online = online
        if not online and self._is_capturing:
            self.stop_capture()

    def is_available(self) -> bool:
        """Checks if a valid audio input device is available."""
        dev = self._device_mgr.get_default_input_device()
        return dev is not None

    def is_capturing(self) -> bool:
        """Returns True if the microphone is currently capturing audio."""
        return self._is_capturing

    def inject_audio_for_test(self, audio_bytes: bytes) -> None:
        """Injects pre-recorded audio bytes for deterministic unit testing."""
        self._injected_audio = audio_bytes

    def start_capture(self) -> None:
        """Starts the capture session."""
        if not self._online:
            raise PermissionError("Assistant is OFFLINE: Microphone capture is strictly forbidden.")
        if not self.is_available() and self._injected_audio is None:
            raise RuntimeError("No microphone input device is available on the system.")
        self._is_capturing = True

    def stop_capture(self) -> None:
        """Stops the active capture session and releases audio device buffers."""
        self._is_capturing = False
        if self._audio_source is not None:
            try:
                self._audio_source.stop()
            except Exception as exc:
                logger.debug("Error stopping audio source: %s", exc)
            self._audio_source = None
            self._io_device = None

    def capture_phrase(self, timeout_seconds: float = 4.0) -> bytes:
        """
        Captures an audio phrase up to timeout_seconds.
        
        Guarantees:
        - Rejects immediately if assistant is OFFLINE.
        - Guarantees return within timeout_seconds without infinite loops.
        - Returns WAV container bytes (16kHz, mono, 16-bit PCM).
        """
        if not self._online:
            raise PermissionError("Assistant is OFFLINE: Microphone capture is strictly forbidden.")

        # Test injection path
        if self._injected_audio is not None:
            time.sleep(0.05)  # Simulate brief capture latency
            data = self._injected_audio
            self._injected_audio = None
            return data

        self.start_capture()
        captured_chunks = []

        try:
            from PySide6.QtCore import QBuffer, QByteArray, QIODevice
            from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices

            fmt = QAudioFormat()
            fmt.setSampleRate(self._sample_rate)
            fmt.setChannelCount(self._channels)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

            default_dev = QMediaDevices.defaultAudioInput()
            if not default_dev or not default_dev.isFormatSupported(fmt):
                # Fallback format if needed
                fmt = default_dev.preferredFormat() if default_dev else fmt

            self._audio_source = QAudioSource(default_dev, fmt)
            qbyte_array = QByteArray()
            qbuffer = QBuffer(qbyte_array)
            qbuffer.open(QIODevice.OpenModeFlag.ReadWrite)

            self._audio_source.start(qbuffer)

            # Record for duration with frequent checks of online status and timeout
            # Keep Qt event queue running so QAudioSource receives OS driver buffers
            from PySide6.QtCore import QCoreApplication

            start_time = time.time()
            while time.time() - start_time < timeout_seconds:
                if not self._online or not self._is_capturing:
                    break
                QCoreApplication.processEvents()
                time.sleep(0.04)

            self._audio_source.stop()
            raw_pcm = bytes(qbyte_array.data())
            qbuffer.close()

            if not raw_pcm:
                # If buffer is empty (e.g. muted virtual mic), return minimal silent WAV
                silent_pcm = b"\x00" * int(self._sample_rate * 0.5 * 2)
                return create_wav_bytes(silent_pcm, sample_rate=self._sample_rate)

            return create_wav_bytes(raw_pcm, sample_rate=self._sample_rate)

        except Exception as exc:
            logger.warning("Native microphone capture fallback: %s", exc)
            # Safe synthetic silent WAV fallback (prevents application crash)
            silent_pcm = b"\x00" * int(self._sample_rate * 0.5 * 2)
            return create_wav_bytes(silent_pcm, sample_rate=self._sample_rate)
        finally:
            self.stop_capture()
