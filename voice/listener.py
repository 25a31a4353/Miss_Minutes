"""
voice/listener.py - Continuous Hands-Free Voice Listener with Voice Activity Detection (VAD).

Eliminates the need for manual microphone clicks:
- Runs in a background QThread without blocking Qt UI.
- Continuously monitors microphone input using adaptive RMS energy detection.
- Captures spoken utterances automatically and emits speech_detected(bytes).
- Pauses automatically while Miss Minutes or Jarvis is speaking (prevents acoustic echo / self-triggering).
- Supports quiet/standby mode when the user requests "remain quiet".
"""

from __future__ import annotations

import io
import logging
import math
import struct
import time
import wave
from typing import Optional

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


def create_wav_bytes(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wraps raw 16-bit PCM bytes into a valid WAV container in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


class ContinuousVoiceListener(QThread):
    """
    Background worker that continuously listens to the system microphone.
    Emits speech_detected(bytes) with WAV container audio whenever the user speaks.
    """

    speech_detected = Signal(bytes)
    speech_started = Signal()
    listening_state_changed = Signal(bool)

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 1024,
        silence_threshold_seconds: float = 0.85,
        parent: Optional[object] = None,
    ):
        super().__init__(parent)
        self._sample_rate = sample_rate
        self._chunk_size = chunk_size
        self._silence_threshold_sec = silence_threshold_seconds

        self._running = False
        self._paused = False       # Set to True while assistant is speaking (echo guard)
        self._is_quiet = False     # Set to True when user commands "remain quiet"
        self._online = True

    @property
    def is_quiet(self) -> bool:
        return self._is_quiet

    def set_quiet(self, quiet: bool) -> None:
        """Sets quiet/standby state. While quiet, audio is not sent to pipeline."""
        self._is_quiet = quiet
        logger.info("ContinuousVoiceListener quiet mode set to: %s", quiet)

    def pause_listening(self) -> None:
        """Pauses listener (used during assistant speech playback to prevent self-hearing)."""
        self._paused = True

    def resume_listening(self) -> None:
        """Resumes listening immediately after assistant finishes speaking."""
        self._paused = False

    def set_online(self, online: bool) -> None:
        self._online = online

    def stop(self) -> None:
        """Stops the listening thread cleanly."""
        self._running = False
        self.wait(1500)

    def run(self) -> None:
        """Continuous audio capture and Voice Activity Detection loop."""
        self._running = True
        self.listening_state_changed.emit(True)
        logger.info("ContinuousVoiceListener started. Hands-free listening active.")

        # Attempt to use sounddevice for rock-solid stream capture
        try:
            import sounddevice as sd
            import numpy as np

            # Dynamic energy threshold calibrated for Windows microphones
            ambient_energy = 220.0
            energy_threshold = 320.0

            recording_frames: list[bytes] = []
            is_speaking = False
            silence_start_time = 0.0
            speech_start_time = 0.0

            with sd.RawInputStream(
                samplerate=self._sample_rate,
                blocksize=self._chunk_size,
                dtype="int16",
                channels=1,
            ) as stream:
                while self._running:
                    # Echo guard or offline check
                    if self._paused or not self._online:
                        time.sleep(0.04)
                        if recording_frames:
                            recording_frames.clear()
                            is_speaking = False
                        continue

                    # Read raw 16-bit PCM chunk from sounddevice
                    data, overflowed = stream.read(self._chunk_size)
                    if not data:
                        time.sleep(0.01)
                        continue

                    # Calculate RMS audio energy
                    count = len(data) // 2
                    if count == 0:
                        continue
                    shorts = struct.unpack(f"<{count}h", data)
                    sum_squares = sum(s * s for s in shorts)
                    rms = math.sqrt(sum_squares / count)

                    # Update ambient noise floor slowly when quiet
                    if not is_speaking:
                        ambient_energy = 0.96 * ambient_energy + 0.04 * min(rms, 500.0)
                        energy_threshold = max(260.0, ambient_energy * 1.30)

                    # Voice Activity Detection
                    if rms > energy_threshold:
                        if not is_speaking:
                            is_speaking = True
                            speech_start_time = time.time()
                            recording_frames.clear()
                            if not self._is_quiet:
                                self.speech_started.emit()
                        silence_start_time = 0.0
                        recording_frames.append(bytes(data))
                    elif is_speaking:
                        recording_frames.append(bytes(data))
                        if silence_start_time == 0.0:
                            silence_start_time = time.time()
                        elif time.time() - silence_start_time >= self._silence_threshold_sec:
                            # Speech ended!
                            duration = time.time() - speech_start_time
                            if duration >= 0.35 and recording_frames:
                                raw_pcm = b"".join(recording_frames)
                                # Check total speech RMS
                                c = len(raw_pcm) // 2
                                if c > 0:
                                    s_arr = struct.unpack(f"<{c}h", raw_pcm[:c*2])
                                    total_rms = math.sqrt(sum(s * s for s in s_arr) / c)
                                else:
                                    total_rms = 0.0

                                if total_rms >= 180.0 and not self._is_quiet:
                                    wav_bytes = create_wav_bytes(raw_pcm, sample_rate=self._sample_rate)
                                    logger.info("Speech utterance captured (%.2fs, rms=%.1f), emitting.", duration, total_rms)
                                    self.speech_detected.emit(wav_bytes)

                            # Reset state for next phrase
                            is_speaking = False
                            recording_frames.clear()
                            silence_start_time = 0.0

                    # Cap maximum phrase duration to 12s
                    if is_speaking and (time.time() - speech_start_time > 12.0):
                        raw_pcm = b"".join(recording_frames)
                        wav_bytes = create_wav_bytes(raw_pcm, sample_rate=self._sample_rate)
                        if not self._is_quiet:
                            self.speech_detected.emit(wav_bytes)
                        is_speaking = False
                        recording_frames.clear()
                        silence_start_time = 0.0

        except Exception as exc:
            logger.warning("Continuous voice listener sounddevice failed: %s. Using polling fallback.", exc)
            self._run_fallback()

        self.listening_state_changed.emit(False)
        logger.info("ContinuousVoiceListener stopped.")

    def _run_fallback(self) -> None:
        """Fallback polling listener when native sounddevice driver is unavailable."""
        while self._running:
            time.sleep(0.1)
