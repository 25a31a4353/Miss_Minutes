"""
voice/device.py - Audio Hardware Device Discovery and Enumeration.

Provides safe discovery of local audio input (microphones) and output (speakers) devices.
Integrates with Windows native devices via PySide6.QtMultimedia when available,
with graceful fallbacks for headless or test environments.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioDeviceInfo:
    """Information regarding a local audio device."""
    device_id: int
    name: str
    is_input: bool
    is_default: bool = False
    channels: int = 2
    default_sample_rate: int = 44100


class AudioDeviceManager:
    """
    Manager for audio device enumeration and selection on Windows.
    
    Guarantees:
    - Queries real Windows Core Audio / WASAPI devices via QtMultimedia when present.
    - Gracefully falls back to safe mock descriptors in headless or virtual test environments.
    - Never throws unhandled driver exceptions during device enumeration.
    """

    def list_input_devices(self) -> List[AudioDeviceInfo]:
        """Lists available audio input devices (microphones)."""
        try:
            from PySide6.QtMultimedia import QMediaDevices
            inputs = QMediaDevices.audioInputs()
            if inputs:
                result = []
                for idx, dev in enumerate(inputs):
                    desc = dev.description() or f"Microphone {idx}"
                    result.append(
                        AudioDeviceInfo(
                            device_id=idx,
                            name=desc,
                            is_input=True,
                            is_default=dev.isDefault(),
                            channels=1,
                            default_sample_rate=16000,
                        )
                    )
                return result
        except Exception as exc:
            logger.debug("QtMultimedia device discovery fallback: %s", exc)

        # Fallback descriptor for tests or headless environments
        return [
            AudioDeviceInfo(
                device_id=0,
                name="Default System Microphone",
                is_input=True,
                is_default=True,
                channels=1,
                default_sample_rate=16000,
            )
        ]

    def list_output_devices(self) -> List[AudioDeviceInfo]:
        """Lists available audio output devices (speakers/headphones)."""
        try:
            from PySide6.QtMultimedia import QMediaDevices
            outputs = QMediaDevices.audioOutputs()
            if outputs:
                result = []
                for idx, dev in enumerate(outputs):
                    desc = dev.description() or f"Speaker {idx}"
                    result.append(
                        AudioDeviceInfo(
                            device_id=idx,
                            name=desc,
                            is_input=False,
                            is_default=dev.isDefault(),
                            channels=2,
                            default_sample_rate=48000,
                        )
                    )
                return result
        except Exception as exc:
            logger.debug("QtMultimedia device discovery fallback: %s", exc)

        return [
            AudioDeviceInfo(
                device_id=0,
                name="Default System Speakers",
                is_input=False,
                is_default=True,
                channels=2,
                default_sample_rate=48000,
            )
        ]

    def get_default_input_device(self) -> Optional[AudioDeviceInfo]:
        inputs = self.list_input_devices()
        for dev in inputs:
            if dev.is_default:
                return dev
        return inputs[0] if inputs else None

    def get_default_output_device(self) -> Optional[AudioDeviceInfo]:
        outputs = self.list_output_devices()
        for dev in outputs:
            if dev.is_default:
                return dev
        return outputs[0] if outputs else None
