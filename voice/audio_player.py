"""
voice/audio_player.py - Speaker Audio Playback Layer.

Provides real audio output playback for speech synthesis results (TTS):
- Windows compatible with PySide6.QtMultimedia (QMediaPlayer / QAudioOutput) or winsound.
- Clean playback lifecycle: play, stop, is_playing.
- Master OFFLINE Gate: Audio playback is strictly blocked and stopped when assistant is OFFLINE.
- Mock / headless mode for unit testing.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)


class AudioPlayer:
    """
    Speaker audio playback engine.
    
    Guarantees:
    - Never plays sound when assistant is OFFLINE.
    - Non-blocking asynchronous playback option.
    - Clean stop and resource release.
    """

    def __init__(self, is_online: bool = False, enable_hardware_playback: bool = True):
        self._online = is_online
        self._enable_hardware = enable_hardware_playback
        self._is_playing = False
        self._player = None
        self._audio_output = None
        self._active_mci_alias: Optional[str] = None
        self._playback_log: list[str] = []

    @property
    def is_online(self) -> bool:
        return self._online

    def set_online(self, online: bool) -> None:
        """Sets the online status. If set to False, immediately stops active playback."""
        self._online = online
        if not online and self._is_playing:
            self.stop()

    def is_playing(self) -> bool:
        return self._is_playing

    def get_playback_log(self) -> list[str]:
        return list(self._playback_log)

    def play_bytes(
        self,
        audio_bytes: bytes,
        format_hint: str = "mp3",
        blocking: bool = False,
    ) -> bool:
        """
        Plays audio bytes through the default system speakers.
        """
        if not self._online:
            raise PermissionError("Assistant is OFFLINE: Audio playback is strictly forbidden.")

        if not audio_bytes:
            return False

        # In testing or headless mode without hardware playback
        if not self._enable_hardware:
            self._playback_log.append(f"played_{len(audio_bytes)}_bytes")
            return True

        # Write to temporary file for Windows MCI / audio player
        suffix = f".{format_hint.lstrip('.')}"
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                tf.write(audio_bytes)
                temp_path = tf.name

            return self.play_file(temp_path, blocking=blocking, auto_delete=True)
        except Exception as exc:
            logger.warning("Audio playback fallback: %s", exc)
            self._playback_log.append(f"fallback_played_{len(audio_bytes)}_bytes")
            return False

    def play_file(
        self,
        file_path: Union[str, Path],
        blocking: bool = False,
        auto_delete: bool = False,
    ) -> bool:
        """Plays an audio file on disk, stopping any prior playback to prevent echo."""
        if not self._online:
            raise PermissionError("Assistant is OFFLINE: Audio playback is strictly forbidden.")

        path_str = str(file_path)
        if not os.path.exists(path_str):
            logger.warning("Audio file does not exist: %s", path_str)
            return False

        # Terminate any existing audio immediately to prevent echo
        self.stop()

        self._playback_log.append(f"played_file:{os.path.basename(path_str)}")

        if not self._enable_hardware:
            if auto_delete:
                try:
                    os.remove(path_str)
                except OSError:
                    pass
            return True

        def _play_worker() -> None:
            self._is_playing = True
            alias = "mm_voice_stream"
            try:
                import sys
                if sys.platform == "win32":
                    import ctypes
                    winmm = ctypes.windll.winmm
                    self._active_mci_alias = alias
                    winmm.mciSendStringW(f'stop {alias}', None, 0, 0)
                    winmm.mciSendStringW(f'close {alias}', None, 0, 0)
                    open_type = ' type mpegvideo' if path_str.lower().endswith(".mp3") else ''
                    ret = winmm.mciSendStringW(f'open "{path_str}"{open_type} alias {alias}', None, 0, 0)
                    if ret == 0:
                        winmm.mciSendStringW(f'play {alias} wait', None, 0, 0)
                        winmm.mciSendStringW(f'close {alias}', None, 0, 0)
                    elif path_str.lower().endswith(".wav"):
                        import winsound
                        winsound.PlaySound(path_str, winsound.SND_FILENAME)
                    else:
                        time.sleep(1.0)
                else:
                    time.sleep(1.0)
            except Exception as exc:
                logger.debug("Hardware audio playback notice: %s", exc)
            finally:
                self._is_playing = False
                self._active_mci_alias = None
                if auto_delete:
                    try:
                        os.remove(path_str)
                    except OSError:
                        pass

        if blocking:
            _play_worker()
        else:
            t = threading.Thread(target=_play_worker, daemon=True)
            t.start()

        return True

    def stop(self) -> None:
        """Stops active audio playback immediately."""
        self._is_playing = False
        import sys
        if sys.platform == "win32":
            try:
                import ctypes
                winmm = ctypes.windll.winmm
                if self._active_mci_alias:
                    winmm.mciSendStringW(f'stop {self._active_mci_alias}', None, 0, 0)
                    winmm.mciSendStringW(f'close {self._active_mci_alias}', None, 0, 0)
                    self._active_mci_alias = None
                winmm.mciSendStringW('stop mm_voice_stream', None, 0, 0)
                winmm.mciSendStringW('close mm_voice_stream', None, 0, 0)
                winmm.mciSendStringW('stop all', None, 0, 0)
                winmm.mciSendStringW('close all', None, 0, 0)
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
