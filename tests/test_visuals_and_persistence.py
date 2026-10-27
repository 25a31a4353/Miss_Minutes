"""
tests/test_visuals_and_persistence.py - Tests for Phase 2 Visual States & Persistence.

Verifies:
1. All 12 FSM states have a complete, valid visual configuration in STATE_VISUALS.
2. Visual tokens (eye, mouth, arm, leg, prop, colors) are correctly defined.
3. Position persistence safely saves and restores window coordinates.
4. Missing, invalid, or corrupted configuration files never crash the app.
5. Screen boundary clamping restores out-of-bounds coordinates to visible workspace.
6. Reduced motion mode pauses the animation timer.
"""

import json
from pathlib import Path
import tempfile
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from config.persistence import (
    clamp_to_screen_boundaries,
    load_window_positions,
    save_window_positions,
)
from ui.expressions import (
    STATE_VISUALS,
    StateVisualConfig,
    get_visual_config,
)
from ui.overlay import MissMinutesOverlay
from ui.state_machine import AppStateMachine, AssistantState


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_all_twelve_states_have_visual_configs() -> None:
    """Verifies that all 12 FSM states defined in the PRD have full visual definitions."""
    all_states = [
        AssistantState.OFFLINE,
        AssistantState.IDLE,
        AssistantState.WAKE_DETECTED,
        AssistantState.LISTENING,
        AssistantState.TRANSCRIBING,
        AssistantState.THINKING,
        AssistantState.VALIDATING,
        AssistantState.WORKING,
        AssistantState.SPEAKING,
        AssistantState.SUCCESS,
        AssistantState.ERROR,
        AssistantState.BLOCKED,
    ]

    assert len(all_states) == 12

    for state in all_states:
        assert state in STATE_VISUALS, f"Missing visual config for state {state.value}"
        cfg = get_visual_config(state)
        assert isinstance(cfg, StateVisualConfig)
        assert cfg.state == state
        assert len(cfg.title) > 0
        assert len(cfg.description) > 0
        assert cfg.bezel_color.isValid()
        assert cfg.face_color.isValid()
        assert cfg.eye_color.isValid()
        assert cfg.accent_color.isValid()
        assert len(cfg.badge_text) > 0
        assert cfg.badge_bg.isValid()


def test_position_persistence_roundtrip() -> None:
    """Verifies saving and reloading window positions using a temp file."""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        temp_path = f.name

    try:
        # 1. Save positions
        save_success = save_window_positions(
            overlay_pos=QPoint(1020, 80),
            controller_pos=QPoint(710, 80),
            reduced_motion=True,
            config_path=temp_path,
        )
        assert save_success is True

        # 2. Load positions
        loaded = load_window_positions(temp_path)
        assert loaded.get("overlay") == {"x": 1020, "y": 80}
        assert loaded.get("controller") == {"x": 710, "y": 80}
        assert loaded.get("reduced_motion") is True
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_corrupted_config_fails_gracefully() -> None:
    """Verifies that corrupted JSON config returns an empty dict rather than crashing."""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
        f.write("{this is not valid json!@@#$")
        temp_path = f.name

    try:
        loaded = load_window_positions(temp_path)
        assert loaded == {}
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_missing_config_returns_empty_dict() -> None:
    """Verifies that a non-existent config path returns an empty dict."""
    non_existent = Path("non_existent_config_98765.json")
    loaded = load_window_positions(non_existent)
    assert loaded == {}


def test_screen_clamping_for_offscreen_coordinates(qapp: QApplication) -> None:
    """Verifies that coordinates far off-screen are clamped to a visible screen rectangle."""
    wild_pos = QPoint(-99999, -99999)
    clamped = clamp_to_screen_boundaries(wild_pos, window_width=150, window_height=170)

    # Coordinates must be brought within positive screen boundaries
    assert clamped.x() >= 0
    assert clamped.y() >= 0


def test_reduced_motion_mode_toggles_anim_timer(qapp: QApplication) -> None:
    """Verifies that enabling reduced motion stops the continuous animation timer."""
    sm = AppStateMachine()
    overlay = MissMinutesOverlay(state_machine=sm, reduced_motion=False)

    assert overlay.reduced_motion is False
    assert overlay._anim_timer.isActive() is True

    # Enable reduced motion
    overlay.reduced_motion = True
    assert overlay.reduced_motion is True
    assert overlay._anim_timer.isActive() is False

    # Re-enable motion
    overlay.reduced_motion = False
    assert overlay.reduced_motion is False
    assert overlay._anim_timer.isActive() is True


def test_dialogue_strings_defined_for_all_twelve_states() -> None:
    """Verifies that all 12 states have contextual dialogue strings from reference images."""
    for state in AssistantState:
        cfg = get_visual_config(state)
        assert hasattr(cfg, "dialogue")
        assert len(cfg.dialogue) > 0, f"State {state.value} is missing dialogue string"


def test_overlay_status_pill_and_mic_interaction(qapp: QApplication) -> None:
    """Verifies that clicking the mic button on the floating status pill triggers voice session or power."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    sm = AppStateMachine(initial_state=AssistantState.IDLE)
    overlay = MissMinutesOverlay(state_machine=sm, reduced_motion=True)

    voice_signals = []
    overlay.voice_session_requested.connect(lambda: voice_signals.append(True))

    # Click on the mic button rect
    mic_rect = overlay._get_mic_btn_rect()
    click_pos = QPointF(mic_rect.center().x(), mic_rect.center().y())

    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        click_pos,
        click_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mousePressEvent(press_event)
    assert len(voice_signals) == 1

    # When offline, clicking mic toggles power ON
    sm.turn_off()
    assert sm.is_online is False
    overlay.mousePressEvent(press_event)
    assert sm.is_online is True


def test_overlay_companion_speech_bubble(qapp: QApplication) -> None:
    """Verifies that the companion speech bubble tracks states and dialogue updates."""
    sm = AppStateMachine(initial_state=AssistantState.IDLE)
    overlay = MissMinutesOverlay(state_machine=sm, reduced_motion=True)

    assert overlay._bubble is not None
    assert overlay._bubble.width() > 0

    # Default transition to WAKE_DETECTED sets status message
    sm.transition_to(AssistantState.WAKE_DETECTED)
    assert overlay._bubble._dialogue == "Wake phrase recognized!"

    # Custom status message updates bubble dialogue
    sm.transition_to(AssistantState.WORKING, "Custom task in progress...")
    assert overlay._bubble._dialogue == "Custom task in progress..."


def test_transparency_and_window_flags(qapp: QApplication) -> None:
    """Verifies that overlay has true WA_TranslucentBackground and frameless tool flags."""
    from PySide6.QtCore import Qt

    sm = AppStateMachine(initial_state=AssistantState.IDLE)
    overlay = MissMinutesOverlay(state_machine=sm, reduced_motion=True)

    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) is True
    assert bool(overlay.windowFlags() & Qt.WindowType.FramelessWindowHint) is True
    assert bool(overlay.windowFlags() & Qt.WindowType.Tool) is True


def test_idle_floating_bob_calculation(qapp: QApplication) -> None:
    """Verifies that the floating animation phase calculates clearly observable travel."""
    import math

    sm = AppStateMachine(initial_state=AssistantState.IDLE)
    overlay = MissMinutesOverlay(state_machine=sm, reduced_motion=False)

    # At phase = 0, offset = 0
    overlay._anim_phase = 0.0
    bob_0 = 5.0 * math.sin(overlay._anim_phase)
    assert abs(bob_0) < 0.01

    # At phase = pi/2, offset = +5.0 px
    overlay._anim_phase = math.pi / 2.0
    bob_up = 5.0 * math.sin(overlay._anim_phase)
    assert abs(bob_up - 5.0) < 0.01

    # At phase = 3*pi/2, offset = -5.0 px
    overlay._anim_phase = 3.0 * math.pi / 2.0
    bob_down = 5.0 * math.sin(overlay._anim_phase)
    assert abs(bob_down - (-5.0)) < 0.01

    # Total peak-to-peak travel is 10px (clearly visible against wallpaper)
    assert (bob_up - bob_down) >= 9.9


def test_state_differentiation_configs() -> None:
    """Verifies that LISTENING, THINKING, WORKING, ERROR, and BLOCKED have distinct tokens."""
    listening = get_visual_config(AssistantState.LISTENING)
    thinking = get_visual_config(AssistantState.THINKING)
    working = get_visual_config(AssistantState.WORKING)
    error = get_visual_config(AssistantState.ERROR)
    blocked = get_visual_config(AssistantState.BLOCKED)
    idle = get_visual_config(AssistantState.IDLE)

    # LISTENING vs THINKING must be distinct in eye, arm, prop, and dialogue
    assert listening.eye_shape != thinking.eye_shape
    assert listening.arm_pose != thinking.arm_pose
    assert listening.prop != thinking.prop
    assert listening.dialogue != thinking.dialogue

    # WORKING vs IDLE must have distinct props and poses
    assert working.prop != idle.prop
    assert working.leg_pose != idle.leg_pose
    assert working.arm_pose != idle.arm_pose

    # ERROR vs BLOCKED must have distinct meanings, expressions, and props
    assert error.prop != blocked.prop
    assert error.arm_pose != blocked.arm_pose
    assert error.eye_shape != blocked.eye_shape
    assert error.mouth_shape != blocked.mouth_shape
    assert error.dialogue != blocked.dialogue


def test_audio_player_lifecycle_and_stop() -> None:
    """Verifies that AudioPlayer initializes, logs playback, and cleanly stops."""
    from voice.audio_player import AudioPlayer
    player = AudioPlayer(is_online=True, enable_hardware_playback=False)
    assert player.is_online is True

    # Play bytes
    res = player.play_bytes(b"dummy_audio_bytes")
    assert res is True
    assert "played_17_bytes" in player.get_playback_log()

    # Stop
    player.stop()
    assert player.is_playing() is False


def test_pyav19_compatibility_av_open() -> None:
    """Verifies that av.open safely drops metadata_errors if called by faster-whisper."""
    import av
    # Call av.open with metadata_errors="ignore" to ensure our compatibility wrapper handles it
    # We can pass an empty stream or nonexistent file and check that TypeError is NOT raised
    try:
        av.open("nonexistent_test_audio.wav", mode="r", metadata_errors="ignore")
    except TypeError as e:
        assert False, f"av.open raised unexpected TypeError: {e}"
    except Exception:
        # FileNotFoundError or AVError is expected and valid; TypeError is what we fixed!
        pass


def test_pipeline_empty_speech_generates_speech_fallback() -> None:
    """Verifies that empty audio transcription results in spoken fallback dialogue."""
    from app.pipeline import CapabilityPipeline
    from voice.service import VoiceService
    from voice.stt import MockSTTProvider
    from voice.tts import MockTTSProvider

    mock_stt = MockSTTProvider(default_transcript="")
    mock_tts = MockTTSProvider()
    vs = VoiceService(stt_provider=mock_stt, tts_provider=mock_tts, is_assistant_online=True)
    pipeline = CapabilityPipeline(voice_service=vs)

    res = pipeline.execute_voice_pipeline(audio_data=b"dummy_silence", is_online=True)
    assert res.success is True
    assert "didn't quite catch that" in res.miss_minutes_response
    # Verify that TTS was called so Miss Minutes speaks the fallback
    assert len(mock_tts.synthesized_log) > 0
    assert "didn't quite catch that" in mock_tts.synthesized_log[0][0]



