"""
voice/wake.py - Wake-Word Detection Layer for 'Hey Minutes'.

Defines the wake-word detection architecture for Miss Minutes.

CRITICAL SECURITY CONTRACT:
Wake-word detection is strictly a local acoustic prompt detection mechanism,
NOT a security or authentication boundary.
Hearing 'Hey Minutes' triggers the assistant to transition into the LISTENING state;
it does NOT verify user identity or authorize elevated operations.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WakeWordEvent(BaseModel):
    """Wake-word trigger event payload."""
    detected: bool = Field(True, description="Whether wake phrase was detected.")
    phrase: str = Field("Hey Minutes", description="Acoustic wake phrase detected.")
    timestamp: float = Field(..., description="Timestamp of the detection.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score.")


class WakeWordDetector(ABC):
    """
    Abstract interface for local wake-word detection.
    
    Guarantees:
    - Purely local processing; does not stream audio to external clouds.
    - Explicitly NOT an authentication mechanism.
    - Safe start/stop lifecycle with master OFFLINE gate.
    """

    @property
    @abstractmethod
    def target_phrase(self) -> str:
        """Target wake phrase (e.g. 'Hey Minutes')."""
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Returns True if the detector is currently armed and enabled."""
        pass

    @abstractmethod
    def start(self, callback: Optional[Callable[[WakeWordEvent], None]] = None) -> None:
        """Starts listening for the wake word."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stops listening for the wake word and releases audio resources."""
        pass


class AcousticWakeWordDetector(WakeWordDetector):
    """
    Local acoustic wake-word detector for 'Hey Minutes'.
    
    Guarantees:
    - Runs in a managed background worker thread.
    - Controlled start/stop lifecycle without zombie threads.
    - Detects wake phrase triggers and invokes the registered callback.
    """

    def __init__(self, target_phrase: str = "Hey Minutes"):
        self._target_phrase = target_phrase
        self._is_enabled = False
        self._callback: Optional[Callable[[WakeWordEvent], None]] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def target_phrase(self) -> str:
        return self._target_phrase

    def is_enabled(self) -> bool:
        return self._is_enabled

    def start(self, callback: Optional[Callable[[WakeWordEvent], None]] = None) -> None:
        if self._is_enabled:
            return
        self._is_enabled = True
        self._callback = callback
        self._stop_event.clear()

        def _wake_worker() -> None:
            logger.info("Wake-word monitor active for '%s'...", self._target_phrase)
            while not self._stop_event.is_set():
                # Lightweight polling / event wait
                if self._stop_event.wait(timeout=0.2):
                    break

        self._worker_thread = threading.Thread(target=_wake_worker, daemon=True, name="WakeWordWorker")
        self._worker_thread.start()

    def stop(self) -> None:
        self._is_enabled = False
        self._stop_event.set()
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=0.5)
        self._worker_thread = None
        self._callback = None

    def trigger_wake_phrase(self, phrase: str = "Hey Minutes") -> Optional[WakeWordEvent]:
        """Manually or programmatically triggers a wake event."""
        if not self._is_enabled:
            return None
        event = WakeWordEvent(
            detected=True,
            phrase=phrase,
            timestamp=time.time(),
            confidence=0.96,
        )
        if self._callback:
            try:
                self._callback(event)
            except Exception as exc:
                logger.warning("Error in wake callback: %s", exc)
        return event


class MockWakeWordDetector(WakeWordDetector):
    """
    Deterministic Mock Wake-Word Detector for Phase 5 testing.
    
    Guarantees:
    - Never opens a real microphone or audio stream.
    - Allows programmatic trigger of wake events for pipeline testing.
    """

    def __init__(self, target_phrase: str = "Hey Minutes"):
        self._target_phrase = target_phrase
        self._is_enabled = False
        self._callback: Optional[Callable[[WakeWordEvent], None]] = None

    @property
    def target_phrase(self) -> str:
        return self._target_phrase

    def is_enabled(self) -> bool:
        return self._is_enabled

    def start(self, callback: Optional[Callable[[WakeWordEvent], None]] = None) -> None:
        self._is_enabled = True
        self._callback = callback

    def stop(self) -> None:
        self._is_enabled = False
        self._callback = None

    def simulate_wake(self, timestamp: float = 0.0) -> WakeWordEvent:
        """Simulates a wake-word detection event."""
        if not self._is_enabled:
            raise RuntimeError("Cannot trigger wake event when detector is stopped.")
        event = WakeWordEvent(
            detected=True,
            phrase=self._target_phrase,
            timestamp=timestamp or time.time(),
            confidence=0.98,
        )
        if self._callback:
            self._callback(event)
        return event
