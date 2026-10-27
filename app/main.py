"""
app/main.py - Entry point and Application Coordinator for Miss Minutes.

Responsibilities:
- Initializes Qt Application lifecycle cleanly.
- Initializes Dual-Agent Foundation (Miss Minutes & Jarvis) with secure Message Bus.
- Restores and safely clamps window positions from ~/.miss_minutes/config.json.
- Binds Settings, State Machine, Overlay, Controller, and Agents together.
- Connects reduced-motion, position persistence, and delegation demonstration hooks.
- Ensures graceful shutdown without orphaned resources or hanging threads.
"""

from __future__ import annotations

import re
import sys
from typing import Optional

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from agents import (
    AgentBusError,
    AgentId,
    AgentMessage,
    AgentMessageBus,
    MessageType,
    MissMinutesAgent,
    SharedBoundedContext,
)
from jarvis import Jarvis
from config.persistence import (
    clamp_to_screen_boundaries,
    load_window_positions,
    save_window_positions,
)
from config.settings import AppSettings, load_settings
from ui.controller import MissMinutesController
from ui.overlay import MissMinutesOverlay
from ui.state_machine import AppStateMachine, AssistantState
from app.pipeline import CapabilityPipeline, PipelineExecutionResult
from voice.service import VoiceService
from voice.listener import ContinuousVoiceListener


class MissMinutesApp(QObject):
    """
    Main application coordinator encapsulating Qt lifecycle and dual-agent foundation.
    """

    def __init__(
        self,
        settings: Optional[AppSettings] = None,
        qapp: Optional[QApplication] = None,
        action_executor: Optional[Any] = None,
    ) -> None:
        super().__init__()
        self._settings = settings or load_settings()
        self._qapp = qapp or QApplication.instance() or QApplication(sys.argv)

        # Set application metadata
        self._qapp.setApplicationName(self._settings.app_name)
        self._qapp.setOrganizationName("MissMinutes")

        # 1. Load saved preferences and positions
        self._saved_prefs = load_window_positions()
        self._reduced_motion = bool(self._saved_prefs.get("reduced_motion", False))

        # 2. Initialize Authoritative State Machine
        init_state = (
            AssistantState.IDLE
            if self._settings.start_state == "IDLE"
            else AssistantState.OFFLINE
        )
        self._state_machine = AppStateMachine(initial_state=init_state)

        # 3. Initialize Dual-Agent Foundation (Miss Minutes & Jarvis)
        self._context = SharedBoundedContext(max_turns=10)
        self._bus = AgentMessageBus(
            state_machine=self._state_machine,
            context=self._context,
        )
        import jarvis_brain
        self._ai_provider = jarvis_brain.get_ai_provider()
        self._miss_minutes_agent = MissMinutesAgent(ai_provider=self._ai_provider)
        self._jarvis = Jarvis()
        self._bus.register_agent(self._miss_minutes_agent)
        self._bus.register_agent(self._jarvis)

        # 4. Build UI Components
        self._overlay = MissMinutesOverlay(
            state_machine=self._state_machine,
            always_on_top=self._settings.always_on_top,
            reduced_motion=self._reduced_motion,
        )
        self._controller = MissMinutesController(
            state_machine=self._state_machine,
            reduced_motion=self._reduced_motion,
        )

        # 4b. Initialize Phase 5 Real Voice Service & Capability Pipeline
        self._voice_service = VoiceService(is_assistant_online=self._state_machine.is_online)
        self._state_machine.state_changed.connect(
            lambda new_s, old_s: self._voice_service.set_online(new_s != AssistantState.OFFLINE)
        )
        self._pipeline = CapabilityPipeline(
            ai_provider=self._ai_provider,
            action_executor=action_executor,
            voice_service=self._voice_service,
            message_bus=self._bus,
            context=self._context,
        )
        self._voice_session_busy = False

        # 4c. Initialize Continuous Hands-Free Voice Listener
        self._continuous_listener = ContinuousVoiceListener(parent=self)
        self._continuous_listener.speech_started.connect(self._on_continuous_speech_started)
        self._continuous_listener.speech_detected.connect(self._on_continuous_speech_detected)
        self._state_machine.state_changed.connect(
            lambda new_s, old_s: self._continuous_listener.set_online(new_s != AssistantState.OFFLINE)
        )

        # 5. Wire Interaction Signals
        self._overlay.controller_toggle_requested.connect(self._toggle_controller)
        self._controller.exit_requested.connect(self.shutdown)
        self._controller.reduced_motion_toggled.connect(self._on_reduced_motion_toggled)
        self._controller.delegation_demo_requested.connect(self.run_delegation_demo)
        self._controller.capability_demo_requested.connect(self.run_capability_demo)
        self._controller.voice_session_requested.connect(self.run_voice_interaction)
        self._overlay.voice_session_requested.connect(self.run_voice_interaction)

        # Position persistence signals
        self._overlay.position_changed.connect(self._on_overlay_moved)
        self._controller.position_changed.connect(self._on_controller_moved)

        self._qapp.aboutToQuit.connect(self._on_about_to_quit)

        # 6. Position Windows with multi-monitor verification
        self._position_windows()

    @property
    def state_machine(self) -> AppStateMachine:
        return self._state_machine

    @property
    def overlay(self) -> MissMinutesOverlay:
        return self._overlay

    @property
    def controller(self) -> MissMinutesController:
        return self._controller

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def bus(self) -> AgentMessageBus:
        return self._bus

    @property
    def miss_minutes_agent(self) -> MissMinutesAgent:
        return self._miss_minutes_agent

    @property
    def jarvis(self) -> Jarvis:
        return self._jarvis

    @property
    def jarvis_agent(self) -> Jarvis:
        return self._jarvis

    @property
    def pipeline(self) -> CapabilityPipeline:
        return self._pipeline

    @property
    def voice_service(self) -> VoiceService:
        return self._voice_service

    def _on_continuous_speech_started(self) -> None:
        """Triggered immediately when continuous listener detects user voice activity."""
        if self._state_machine.is_online and not getattr(self, "_voice_session_busy", False):
            self._state_machine.transition_to(AssistantState.LISTENING, "Listening to you...")

    def _on_continuous_speech_detected(self, wav_bytes: bytes) -> None:
        """Triggered when user finishes speaking an utterance hands-free."""
        if not self._state_machine.is_online or getattr(self, "_voice_session_busy", False):
            return
        self.run_voice_interaction(audio_data=wav_bytes)

    def run_voice_interaction(
        self,
        audio_data: Optional[bytes] = None,
        language_hint: Optional[str] = None,
    ) -> Optional[PipelineExecutionResult]:
        """
        Executes real voice interaction with turn-taking dialogue:
        LISTENING -> TRANSCRIBING -> THINKING -> WORKING -> SPEAKING (Miss Minutes -> Jarvis) -> IDLE.
        """
        if not self._state_machine.is_online:
            return None

        # Re-entrancy guard
        if getattr(self, "_voice_session_busy", False):
            logger.debug("Voice session already active, ignoring duplicate trigger.")
            return None
        self._voice_session_busy = True

        # Pause continuous listener while processing and speaking (echo cancellation guard)
        if hasattr(self, "_continuous_listener"):
            self._continuous_listener.pause_listening()

        from PySide6.QtCore import QCoreApplication
        import time

        try:
            # Terminate any playing audio
            if self._voice_service.audio_player.is_playing():
                self._voice_service.audio_player.stop()
                time.sleep(0.12)

            # 1. Visual transition to LISTENING
            self._state_machine.transition_to(
                AssistantState.LISTENING,
                "Listening to your voice...",
            )
            QCoreApplication.processEvents()

            # 2. Capture speech from microphone if not pre-captured by continuous listener
            try:
                raw_wav = audio_data if audio_data is not None else self._voice_service.capture_speech()
            except Exception as e:
                self._state_machine.trigger_error_feedback(f"Microphone error: {e}")
                return None

            # 3. Transcribing
            self._state_machine.transition_to(
                AssistantState.TRANSCRIBING,
                "Converting your speech to text...",
            )
            QCoreApplication.processEvents()

            res = self._pipeline.execute_voice_pipeline(
                audio_data=raw_wav,
                language_hint=language_hint,
                is_online=True,
            )

            if not res.success:
                self._state_machine.trigger_error_feedback(res.error_message or "Voice interaction failed.")
                return res

            if not res.raw_transcript:
                fallback_text = res.miss_minutes_response or "I didn't quite catch that, sugar. Could you say that again?"
                self._state_machine.transition_to(AssistantState.SPEAKING, fallback_text)
                QCoreApplication.processEvents()
                try:
                    self._voice_service.speak_text_blocking(fallback_text, agent_name="miss_minutes", language="te")
                except Exception:
                    pass
                self._state_machine.transition_to(AssistantState.IDLE, fallback_text)
                return res

            # 4. Sequential Turn-Taking Speech Output (Miss Minutes then Jarvis)
            # Step 4a: Miss Minutes speaks first
            if res.miss_minutes_response:
                self._state_machine.transition_to(
                    AssistantState.SPEAKING,
                    f"Miss Minutes: {res.miss_minutes_response}",
                )
                QCoreApplication.processEvents()
                try:
                    self._voice_service.speak_text_blocking(
                        res.miss_minutes_response,
                        agent_name="miss_minutes",
                        language="te",
                    )
                except Exception as exc:
                    logger.debug("Miss Minutes TTS error: %s", exc)

            # Step 4b: Jarvis speaks second (turn-taking)
            if res.jarvis_response:
                time.sleep(0.3)
                self._state_machine.transition_to(
                    AssistantState.SPEAKING,
                    f"Jarvis: {res.jarvis_response}",
                )
                QCoreApplication.processEvents()
                try:
                    self._voice_service.speak_text_blocking(
                        res.jarvis_response,
                        agent_name="jarvis",
                        language="te",
                    )
                except Exception as exc:
                    logger.debug("Jarvis TTS error: %s", exc)

            # Step 5: Check if quiet mode was requested
            intent_type = res.intent.intent.value if hasattr(res.intent, "intent") else ""
            if intent_type == "QUIET_STANDBY":
                if hasattr(self, "_continuous_listener"):
                    self._continuous_listener.set_quiet(True)
                self._state_machine.transition_to(
                    AssistantState.IDLE,
                    "Quiet Standby. (Say 'matladu' or click to resume)",
                )
            elif intent_type == "RESUME_LISTENING":
                if hasattr(self, "_continuous_listener"):
                    self._continuous_listener.set_quiet(False)
                self._state_machine.trigger_success_feedback(
                    "Ready and listening...",
                )
            else:
                self._state_machine.trigger_success_feedback(
                    f"Done! {res.miss_minutes_response}",
                )

            return res

        finally:
            self._voice_session_busy = False
            # Resume hands-free listening
            if hasattr(self, "_continuous_listener"):
                self._continuous_listener.resume_listening()

    def run_capability_demo(
        self,
        utterance: str = "Hey Minutes, YouTube open chesi AR Rahman songs play cheyyi",
    ) -> Optional[PipelineExecutionResult]:
        """
        Executes an end-to-end simulation of the Phase 4 capability pipeline:
        WAKE_DETECTED -> TRANSCRIBING -> THINKING -> VALIDATING -> WORKING -> SPEAKING -> SUCCESS.
        """
        if not self._state_machine.is_online:
            return None

        # 1. Wake phrase detected
        self._state_machine.transition_to(
            AssistantState.WAKE_DETECTED,
            "Wake phrase detected: 'Hey Minutes'",
        )

        # 2. Transcribing user utterance
        self._state_machine.transition_to(
            AssistantState.TRANSCRIBING,
            f"Transcribing: \"{utterance}\"",
        )

        # 3. Intent understanding & delegation
        self._state_machine.transition_to(
            AssistantState.THINKING,
            "Miss Minutes: Understanding Telugu-English intent...",
        )

        # 4. Security validation
        self._state_machine.transition_to(
            AssistantState.VALIDATING,
            "Security Validator: checking PLAY_YOUTUBE against allowlist...",
        )

        # 5. Technical action execution
        self._state_machine.transition_to(
            AssistantState.WORKING,
            "Jarvis: executing mock PLAY_YOUTUBE capability...",
        )

        res = self._pipeline.execute_pipeline(utterance, is_online=True)

        if res.success:
            self._state_machine.transition_to(
                AssistantState.SPEAKING,
                f"Miss Minutes: {res.miss_minutes_response}",
            )
            self._state_machine.trigger_success_feedback(
                "Mock playback of 'AR Rahman songs' on YouTube complete (Simulated).",
            )
        else:
            self._state_machine.trigger_error_feedback(res.error_message or "Capability failed.")

        return res

    def run_delegation_demo(self, query: str = "lo-fi beats on YouTube") -> Optional[AgentMessage]:
        """
        Executes a deterministic demonstration of Miss Minutes delegating a technical task
        to Jarvis, receiving the result, and presenting it to the user.
        """
        if not self._state_machine.is_online:
            return None

        # 1. State changes to WORKING
        self._state_machine.transition_to(
            AssistantState.WORKING,
            f"Miss Minutes asking Jarvis to prepare '{query}'...",
        )

        # 2. Delegation message from Miss Minutes to Jarvis
        clean_target = re.sub(r"\s+(?:on|in)\s+youtube", "", query, flags=re.IGNORECASE).strip()
        delegation_msg = AgentMessage(
            sender=AgentId.MISS_MINUTES,
            recipient=AgentId.JARVIS,
            message_type=MessageType.DELEGATION,
            content=f"Jarvis, would you please look up '{clean_target}' on YouTube?",
            metadata={"query": clean_target, "action_hint": "SEARCH_YOUTUBE"},
            requires_response=True,
        )

        try:
            jarvis_reply = self._bus.dispatch(delegation_msg)
            if jarvis_reply and jarvis_reply.message_type == MessageType.RESULT:
                # 3. Miss Minutes translates result for user
                mm_response = self._miss_minutes_agent.receive_message(jarvis_reply, self._context)
                content = mm_response.content if mm_response else jarvis_reply.content
                self._state_machine.trigger_success_feedback(f"Jarvis: {content}")
                return jarvis_reply
            else:
                self._state_machine.trigger_error_feedback("Jarvis could not complete delegation.")
                return None
        except AgentBusError as e:
            self._state_machine.trigger_error_feedback(str(e))
            return None

    def _position_windows(self) -> None:
        """Positions overlay and controller with multi-monitor verification and clamping."""
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return

        geom = screen.availableGeometry()

        # 1. Determine Overlay Position
        overlay_saved = self._saved_prefs.get("overlay")
        if overlay_saved and "x" in overlay_saved and "y" in overlay_saved:
            raw_pos = QPoint(int(overlay_saved["x"]), int(overlay_saved["y"]))
            clamped_pos = clamp_to_screen_boundaries(
                raw_pos, self._overlay.width(), self._overlay.height()
            )
            self._overlay.move(clamped_pos)
        else:
            default_ox = geom.right() - self._overlay.width() - 40
            default_oy = geom.top() + 60
            self._overlay.move(default_ox, default_oy)

        # 2. Determine Controller Position
        ctrl_saved = self._saved_prefs.get("controller")
        if ctrl_saved and "x" in ctrl_saved and "y" in ctrl_saved:
            raw_ctrl_pos = QPoint(int(ctrl_saved["x"]), int(ctrl_saved["y"]))
            clamped_ctrl_pos = clamp_to_screen_boundaries(
                raw_ctrl_pos, self._controller.width(), self._controller.height()
            )
            self._controller.move(clamped_ctrl_pos)
        else:
            default_cx = max(geom.left() + 20, self._overlay.x() - self._controller.width() - 20)
            default_cy = self._overlay.y()
            self._controller.move(default_cx, default_cy)

    def _on_overlay_moved(self, pos: QPoint) -> None:
        save_window_positions(overlay_pos=pos)

    def _on_controller_moved(self, pos: QPoint) -> None:
        save_window_positions(controller_pos=pos)

    def _on_reduced_motion_toggled(self, reduced: bool) -> None:
        self._reduced_motion = reduced
        self._overlay.reduced_motion = reduced
        save_window_positions(reduced_motion=reduced)

    def _toggle_controller(self) -> None:
        """Toggles controller window visibility."""
        if self._controller.isVisible():
            self._controller.hide()
        else:
            self._controller.show()
            self._controller.raise_()
            self._controller.activateWindow()

    def _play_welcome_dialogue(self) -> None:
        """Presents signature modern Telugu + English turn-taking greeting on startup."""
        if not self._state_machine.is_online:
            return
        mm_text = "Hey! Nenu Miss Minutes ni. Enti ivala chala workload undhi anukunta! Neeku eh help kaavalo cheppu, seconds lo complete chesi pedathanu."
        jarvis_text = "Exactly ma'am. Jarvis here, systems fully operational. Just command ivvandi sir, seconds lo take care chestham."
        self._voice_service.speak_turn_taking(mm_text, jarvis_text, language="te")
        self._state_machine.transition_to(AssistantState.IDLE, "Ready and listening...")

    def show(self) -> None:
        """Presents both overlay and controller on screen and activates hands-free listening."""
        self._overlay.show()
        self._controller.show()
        # Activate hands-free listener if online
        if self._state_machine.is_online and not self._continuous_listener.isRunning():
            self._continuous_listener.start()
        # Trigger welcome greeting
        QTimer.singleShot(800, self._play_welcome_dialogue)

    def shutdown(self) -> None:
        """Coordinates clean application shutdown."""
        if hasattr(self, "_continuous_listener"):
            self._continuous_listener.stop()

        # Save positions on shutdown
        save_window_positions(
            overlay_pos=self._overlay.pos(),
            controller_pos=self._controller.pos(),
            reduced_motion=self._reduced_motion,
        )
        self._state_machine.turn_off()
        self._overlay.close()
        self._controller.close()
        self._qapp.quit()

    def _on_about_to_quit(self) -> None:
        """Cleanup hook executed right before Qt event loop terminates."""
        if hasattr(self, "_continuous_listener"):
            self._continuous_listener.stop()
        self._state_machine.turn_off()


def main() -> int:
    """CLI entry point delegating to authoritative root main.py."""
    import main as root_entry
    return root_entry.main()


if __name__ == "__main__":
    sys.exit(main())

