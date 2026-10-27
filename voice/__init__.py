"""
voice/__init__.py - Real Voice Interaction Package for Miss Minutes + Jarvis.

Exports:
- SpeechToTextProvider, FasterWhisperSTTProvider, MockSTTProvider, TranscriptionResult
- TextToSpeechProvider, EdgeTTSProvider, MockTTSProvider, TTSAudioResult
- WakeWordDetector, AcousticWakeWordDetector, MockWakeWordDetector, WakeWordEvent
- MicrophoneDevice, create_wav_bytes
- AudioPlayer
- AgentVoiceProfile, MISS_MINUTES_VOICE_PROFILE, JARVIS_VOICE_PROFILE, get_voice_profile
- AudioDeviceManager, AudioDeviceInfo
- VoiceService
"""

from voice.stt import (
    SpeechToTextProvider,
    TranscriptionResult,
    FasterWhisperSTTProvider,
    MockSTTProvider,
)
from voice.tts import (
    TextToSpeechProvider,
    TTSAudioResult,
    EdgeTTSProvider,
    MockTTSProvider,
)
from voice.wake import (
    WakeWordDetector,
    WakeWordEvent,
    AcousticWakeWordDetector,
    MockWakeWordDetector,
)
from voice.microphone import MicrophoneDevice, create_wav_bytes
from voice.audio_player import AudioPlayer
from voice.voices import (
    AgentVoiceProfile,
    MISS_MINUTES_VOICE_PROFILE,
    JARVIS_VOICE_PROFILE,
    get_voice_profile,
)
from voice.device import AudioDeviceManager, AudioDeviceInfo
from voice.service import VoiceService

__all__ = [
    "SpeechToTextProvider",
    "TranscriptionResult",
    "FasterWhisperSTTProvider",
    "MockSTTProvider",
    "TextToSpeechProvider",
    "TTSAudioResult",
    "EdgeTTSProvider",
    "MockTTSProvider",
    "WakeWordDetector",
    "WakeWordEvent",
    "AcousticWakeWordDetector",
    "MockWakeWordDetector",
    "MicrophoneDevice",
    "create_wav_bytes",
    "AudioPlayer",
    "AgentVoiceProfile",
    "MISS_MINUTES_VOICE_PROFILE",
    "JARVIS_VOICE_PROFILE",
    "get_voice_profile",
    "AudioDeviceManager",
    "AudioDeviceInfo",
    "VoiceService",
]
