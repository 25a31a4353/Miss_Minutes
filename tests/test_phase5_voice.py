"""
tests/test_phase5_voice.py - Comprehensive Test Suite for Phase 5 Real Voice Layer.

Covers:
1. Microphone Device (Windows compatible, lifecycle, timeout guards, test injection)
2. faster-whisper STT (English, Telugu, Code-switching, silence guard)
3. Wake Word Detection (Hey Minutes, non-authenticating contract, lifecycle)
4. Audio Player (Speaker playback, format handling, OFFLINE gate)
5. VoiceService Coordinator (Microphone -> STT -> TTS -> Speaker -> OFFLINE gate)
6. Dual-Agent Voice Synchronization (Miss Minutes vs Jarvis distinct voices)
7. State Machine Transitions with Voice Sessions
"""

from __future__ import annotations

import io
import time
import wave
import pytest

from voice.device import AudioDeviceManager, AudioDeviceInfo
from voice.microphone import MicrophoneDevice, create_wav_bytes
from voice.stt import FasterWhisperSTTProvider, MockSTTProvider, TranscriptionResult
from voice.audio_player import AudioPlayer
from voice.tts import EdgeTTSProvider, MockTTSProvider, TTSAudioResult
from voice.voices import get_voice_profile, MISS_MINUTES_VOICE_PROFILE, JARVIS_VOICE_PROFILE
from voice.wake import AcousticWakeWordDetector, MockWakeWordDetector, WakeWordEvent
from voice.service import VoiceService
import jarvis_voice
from jarvis import Jarvis, get_jarvis
from app.pipeline import CapabilityPipeline, PipelineExecutionResult
from ui.state_machine import AppStateMachine, AssistantState


def _make_dummy_wav(duration_secs: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Helper to generate in-memory dummy WAV bytes for testing."""
    buf = io.BytesIO()
    num_samples = int(sample_rate * duration_secs)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()


# ============================================================================
# 1. MICROPHONE DEVICE & DEVICE ENUMERATION TESTS
# ============================================================================

def test_audio_device_manager_enumeration() -> None:
    """Verifies AudioDeviceManager lists default input and output devices."""
    mgr = AudioDeviceManager()
    inputs = mgr.list_input_devices()
    outputs = mgr.list_output_devices()

    assert len(inputs) >= 1
    assert inputs[0].is_input is True
    assert len(outputs) >= 1
    assert outputs[0].is_input is False

    assert mgr.get_default_input_device() is not None
    assert mgr.get_default_output_device() is not None


def test_microphone_device_offline_enforcement() -> None:
    """Verifies that MicrophoneDevice strictly refuses capture when assistant is OFFLINE."""
    mic = MicrophoneDevice()
    assert mic.is_online is False

    with pytest.raises(PermissionError, match="Assistant is OFFLINE"):
        mic.start_capture()

    with pytest.raises(PermissionError, match="Assistant is OFFLINE"):
        mic.capture_phrase()

    # Turn online
    mic.set_online(True)
    assert mic.is_online is True

    # Switching offline stops active capture
    mic.inject_audio_for_test(_make_dummy_wav())
    mic.start_capture()
    assert mic.is_capturing() is True
    mic.set_online(False)
    assert mic.is_capturing() is False


def test_microphone_device_capture_with_injection() -> None:
    """Verifies capture_phrase returns valid WAV bytes when audio is injected."""
    mic = MicrophoneDevice()
    mic.set_online(True)

    dummy_wav = _make_dummy_wav(0.2)
    mic.inject_audio_for_test(dummy_wav)

    captured = mic.capture_phrase(timeout_seconds=2.0)
    assert captured == dummy_wav
    assert mic.is_capturing() is False


def test_create_wav_bytes_utility() -> None:
    """Verifies raw PCM wrapping creates a valid readable WAV container."""
    raw_pcm = b"\x01\x00" * 800  # 800 samples of 16-bit PCM
    wav_bytes = create_wav_bytes(raw_pcm, sample_rate=16000, channels=1)

    assert wav_bytes.startswith(b"RIFF")
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 800


# ============================================================================
# 2. FASTER-WHISPER SPEECH-TO-TEXT TESTS
# ============================================================================

def test_faster_whisper_availability_and_silence_guard() -> None:
    """Verifies faster-whisper is installed, loads safely, and handles silence cleanly."""
    stt = FasterWhisperSTTProvider(model_size="tiny", device="cpu", compute_type="int8")
    assert stt.provider_id == "faster-whisper"
    assert stt.is_available() is True

    # Transcribe pure silent audio -> must return empty text, not hallucinate
    silent_wav = _make_dummy_wav(duration_secs=0.5)
    res = stt.transcribe(silent_wav)

    assert isinstance(res, TranscriptionResult)
    # Silence guard contract: silence produces empty text without crashing
    assert res.is_empty is True
    assert res.confidence == 0.0


def test_stt_preserves_raw_transcript_and_detects_code_switching() -> None:
    """Verifies that MockSTTProvider and STT contract preserve raw transcript and classify code-switching."""
    mock_stt = MockSTTProvider()

    # English transcript
    mock_stt.set_mock_transcript("Open YouTube and search for quantum computing", language="en")
    res_en = mock_stt.transcribe(b"dummy")
    assert res_en.raw_text == "Open YouTube and search for quantum computing"
    assert res_en.language == "en"
    assert res_en.is_code_switched is False

    # Telugu-English code-switched transcript
    mock_stt.set_mock_transcript("YouTube open chesi AR Rahman songs play cheyyi", language="te-en")
    res_te = mock_stt.transcribe(b"dummy")
    assert res_te.raw_text == "YouTube open chesi AR Rahman songs play cheyyi"
    assert res_te.language == "te-en"
    assert res_te.is_code_switched is True


# ============================================================================
# 3. WAKE-WORD DETECTION & NON-AUTHENTICATION CONTRACT
# ============================================================================

def test_acoustic_wake_word_detector_lifecycle() -> None:
    """Verifies start, stop, and callback dispatch for AcousticWakeWordDetector."""
    detector = AcousticWakeWordDetector("Hey Minutes")
    assert detector.target_phrase == "Hey Minutes"
    assert detector.is_enabled() is False

    events = []

    def _callback(evt: WakeWordEvent) -> None:
        events.append(evt)

    detector.start(callback=_callback)
    assert detector.is_enabled() is True

    # Trigger wake event
    triggered = detector.trigger_wake_phrase("Hey Minutes")
    assert triggered is not None
    assert triggered.detected is True
    assert len(events) == 1
    assert events[0].phrase == "Hey Minutes"

    # Stop detector
    detector.stop()
    assert detector.is_enabled() is False
    assert detector.trigger_wake_phrase("Hey Minutes") is None


def test_wake_word_is_strictly_non_authenticating() -> None:
    """
    CRITICAL SECURITY CONTRACT:
    Wake-word detection is strictly a prompt detector, NEVER authentication.
    """
    detector = MockWakeWordDetector("Hey Minutes")
    detector.start()
    evt = detector.simulate_wake()

    assert evt.detected is True
    assert evt.phrase == "Hey Minutes"
    # Must not contain user verification tokens or credentials
    assert not hasattr(evt, "user_id")
    assert not hasattr(evt, "token")
    assert not hasattr(evt, "is_authorized")


# ============================================================================
# 4. AUDIO PLAYER & SPEAKER OUTPUT
# ============================================================================

def test_audio_player_lifecycle_and_offline_gate() -> None:
    """Verifies AudioPlayer refuses playback when OFFLINE and stops active playback."""
    player = AudioPlayer(is_online=False, enable_hardware_playback=False)

    with pytest.raises(PermissionError, match="Assistant is OFFLINE"):
        player.play_bytes(b"dummy")

    with pytest.raises(PermissionError, match="Assistant is OFFLINE"):
        player.play_file("dummy.wav")

    # Turn online
    player.set_online(True)
    assert player.is_online is True

    # Play dummy bytes in headless/mock mode
    ok = player.play_bytes(b"\x00" * 64, format_hint="mp3")
    assert ok is True
    assert len(player.get_playback_log()) == 1

    # Turning offline resets playing state
    player.set_online(False)
    assert player.is_playing() is False


# ============================================================================
# 5. COORDINATED VOICE SERVICE TESTS
# ============================================================================

def test_voice_service_offline_master_boundary() -> None:
    """Verifies VoiceService blocks all operations when assistant is OFFLINE."""
    svc = VoiceService(is_assistant_online=False)

    with pytest.raises(PermissionError, match="Assistant is OFFLINE"):
        svc.capture_speech()

    with pytest.raises(PermissionError, match="Assistant is OFFLINE"):
        svc.transcribe_audio(b"dummy")

    with pytest.raises(PermissionError, match="Assistant is OFFLINE"):
        svc.speak_text("Hello darling", agent_name="miss_minutes")

    with pytest.raises(PermissionError, match="Assistant is OFFLINE"):
        svc.start_wake_detection()

    with pytest.raises(PermissionError, match="Assistant is OFFLINE"):
        svc.process_voice_interaction()


def test_voice_service_online_interaction_loop() -> None:
    """Verifies complete voice loop: capture -> transcribe -> TTS -> audio output."""
    mock_stt = MockSTTProvider(default_transcript="Open Chrome", language="en")
    mock_tts = MockTTSProvider()
    player = AudioPlayer(is_online=True, enable_hardware_playback=False)
    mic = MicrophoneDevice()
    mic.set_online(True)
    mic.inject_audio_for_test(_make_dummy_wav(0.1))

    svc = VoiceService(
        stt_provider=mock_stt,
        tts_provider=mock_tts,
        microphone=mic,
        audio_player=player,
        is_assistant_online=True,
    )

    # 1. Voice capture + transcription
    res = svc.process_voice_interaction()
    assert res.raw_text == "Open Chrome"
    assert res.language == "en"

    # 2. TTS synthesis for Miss Minutes
    tts_res = svc.speak_text("Right away, sugar!", agent_name="miss_minutes", play_audio=True)
    assert tts_res.voice_used == "en-US-JennyNeural"
    assert len(player.get_playback_log()) >= 1


def test_jarvis_voice_speaks_with_distinct_profile() -> None:
    """Verifies that existing Jarvis speaks through the shared voice service with his male profile."""
    player = AudioPlayer(is_online=True, enable_hardware_playback=False)
    mock_tts = MockTTSProvider()
    svc = VoiceService(tts_provider=mock_tts, audio_player=player, is_assistant_online=True)
    jarvis_voice.set_voice_service(svc)

    # 1. Jarvis speaks English
    res_en = jarvis_voice.speak("Task verified and ready for execution, sir.", language="en", is_online=True)
    assert res_en is not None
    assert res_en.voice_used == "en-GB-RyanNeural"

    # 2. Jarvis speaks Telugu
    res_te = jarvis_voice.speak("Pani purthaindi, sir.", language="te", is_online=True)
    assert res_te is not None
    assert res_te.voice_used == "te-IN-MohanNeural"

    # 3. Blocked when OFFLINE
    res_off = jarvis_voice.speak("Hello", is_online=False)
    assert res_off is None


# ============================================================================
# 6. PIPELINE & GUI VOICE SESSION INTEGRATION
# ============================================================================

def test_pipeline_execute_voice_pipeline_silence_guard() -> None:
    """Verifies execute_voice_pipeline refuses to call actions on silent audio."""
    mock_stt = MockSTTProvider(default_transcript="", language="en")
    svc = VoiceService(stt_provider=mock_stt, is_assistant_online=True)
    pipeline = CapabilityPipeline(voice_service=svc)

    result = pipeline.execute_voice_pipeline(
        audio_data=_make_dummy_wav(0.2),
        is_online=True,
    )

    # Silence contract: clean prompt to retry, NO action capability called
    assert result.success is True
    assert result.raw_transcript == ""
    assert result.capability_request is None
    assert result.capability_result is None
    assert "didn't quite catch that" in result.miss_minutes_response


def test_pipeline_execute_voice_pipeline_with_telugu_speech() -> None:
    """Verifies execute_voice_pipeline parses Telugu-English voice, delegates to Jarvis, and speaks back."""
    mock_stt = MockSTTProvider(
        default_transcript="YouTube open chesi AR Rahman songs play cheyyi",
        language="te-en",
    )
    mock_tts = MockTTSProvider()
    player = AudioPlayer(is_online=True, enable_hardware_playback=False)
    svc = VoiceService(
        stt_provider=mock_stt,
        tts_provider=mock_tts,
        audio_player=player,
        is_assistant_online=True,
    )
    pipeline = CapabilityPipeline(voice_service=svc)

    result = pipeline.execute_voice_pipeline(audio_data=_make_dummy_wav(0.2), is_online=True)

    assert result.success is True
    assert result.raw_transcript == "YouTube open chesi AR Rahman songs play cheyyi"
    assert result.language == "te-en"
    assert result.delegated_to_jarvis is True
    assert result.capability_result is not None
    assert result.capability_result.success is True
    assert result.capability_result.simulated is True
    assert result.tts_result is not None
    assert len(player.get_playback_log()) >= 1


def test_app_run_voice_interaction(qapp) -> None:
    """Verifies MissMinutesApp.run_voice_interaction executes state machine transitions."""
    from app.main import MissMinutesApp

    app = MissMinutesApp(qapp=qapp)

    # 1. Offline: refuses voice interaction
    assert app.state_machine.current_state == AssistantState.OFFLINE
    res_off = app.run_voice_interaction()
    assert res_off is None

    # 2. Online: inject dummy audio and run voice interaction
    app.state_machine.turn_on()
    assert app.state_machine.is_online is True

    # Use mock STT for instant test execution
    app.voice_service._stt = MockSTTProvider(
        default_transcript="Hey Minutes, what time is it?",
        language="en",
    )
    app.voice_service._player._enable_hardware = False

    res_on = app.run_voice_interaction(audio_data=_make_dummy_wav(0.1))
    assert res_on is not None
    assert res_on.success is True
    assert "what time is it" in res_on.raw_transcript
    assert app.state_machine.current_state == AssistantState.SUCCESS

    # Clean shutdown
    app.shutdown()
    assert app.state_machine.current_state == AssistantState.OFFLINE
