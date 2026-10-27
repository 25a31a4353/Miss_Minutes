"""
ui/state_machine.py - Authoritative Finite State Machine for Miss Minutes.

Rules:
- OFFLINE is the single authoritative disabled state.
- In OFFLINE, no action hooks, audio hardware, or AI calls are permitted.
- Emits thread-safe Qt signals on state transitions.
- Supports all 12 states defined in Miss_Minutes_PRD.md Section 5.2.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from PySide6.QtCore import QObject, Signal, QTimer


class AssistantState(str, Enum):
    """
    Assistant Lifecycle States defined in Miss_Minutes_PRD.md Section 5.2.
    """
    OFFLINE = "OFFLINE"              # Disabled; audio/wake/actions stopped
    IDLE = "IDLE"                    # Enabled and waiting for user input / wake phrase
    WAKE_DETECTED = "WAKE_DETECTED"  # Wake phrase recognized
    LISTENING = "LISTENING"          # Capturing audio
    TRANSCRIBING = "TRANSCRIBING"    # Speech to text in progress
    THINKING = "THINKING"            # AI response / reasoning in progress
    VALIDATING = "VALIDATING"        # Checking action against security allowlist
    WORKING = "WORKING"              # Approved action executing on OS
    SPEAKING = "SPEAKING"            # TTS audio output active
    SUCCESS = "SUCCESS"              # Verified action or query success
    ERROR = "ERROR"                  # Operation or network failure
    BLOCKED = "BLOCKED"              # Security layer refused action


class StateTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""
    pass


class AppStateMachine(QObject):
    """
    Authoritative state coordinator for the desktop assistant.
    Thread-safe through Qt Signal/Slot mechanism.
    """

    # Signals: (new_state, old_state)
    state_changed = Signal(AssistantState, AssistantState)
    status_message_changed = Signal(str)

    def __init__(self, initial_state: AssistantState = AssistantState.OFFLINE, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._current_state = initial_state
        self._previous_state = initial_state
        self._status_message = "Assistant is OFF."

        # Timer to auto-return to IDLE after temporary SUCCESS or ERROR states
        self._transient_timer = QTimer(self)
        self._transient_timer.setSingleShot(True)
        self._transient_timer.timeout.connect(self._handle_transient_timeout)

    @property
    def current_state(self) -> AssistantState:
        """The authoritative current application state."""
        return self._current_state

    @property
    def previous_state(self) -> AssistantState:
        """The previous state prior to the last transition."""
        return self._previous_state

    @property
    def status_message(self) -> str:
        """Human-readable status summary."""
        return self._status_message

    @property
    def is_online(self) -> bool:
        """Returns True if the assistant is turned ON (not in OFFLINE state)."""
        return self._current_state != AssistantState.OFFLINE

    @property
    def is_offline(self) -> bool:
        """Returns True if the assistant is turned OFF (in OFFLINE state)."""
        return self._current_state == AssistantState.OFFLINE

    def turn_on(self) -> bool:
        """
        Transitions the assistant from OFFLINE to IDLE.
        Returns True if transition occurred, False if already online.
        """
        if self._current_state == AssistantState.OFFLINE:
            return self.transition_to(AssistantState.IDLE, "Assistant enabled and ready.")
        return False

    def turn_off(self) -> bool:
        """
        Authoritatively cuts off all activity and transitions to OFFLINE.
        Cancels any transient timers or pending actions.
        """
        if self._transient_timer.isActive():
            self._transient_timer.stop()

        if self._current_state != AssistantState.OFFLINE:
            return self.transition_to(AssistantState.OFFLINE, "Assistant turned OFF.")
        return False

    def toggle_power(self) -> AssistantState:
        """Toggles between OFFLINE and IDLE."""
        if self.is_online:
            self.turn_off()
        else:
            self.turn_on()
        return self._current_state

    def can_execute_action(self) -> bool:
        """
        Security gate check:
        Guarantees that no actions can execute if the assistant is OFFLINE.
        """
        return self.is_online

    def request_action_hook(self, action_name: str) -> bool:
        """
        Testable security gate hook for action execution.
        Returns False immediately if OFFLINE.
        """
        if not self.can_execute_action():
            return False
        # When online in Phase 1, we can indicate working/success
        return True

    def transition_to(self, target: AssistantState, message: Optional[str] = None) -> bool:
        """
        Attempts a transition to the target state.
        
        Rules:
        - If current is OFFLINE, only IDLE or OFFLINE is permitted.
        - Transitioning to the current state is a safe no-op.
        - Transient states (SUCCESS, ERROR) automatically schedule a return to IDLE.
        """
        if target == self._current_state:
            if message and message != self._status_message:
                self._status_message = message
                self.status_message_changed.emit(message)
            return True

        # OFFLINE is the master disable state: reject any state other than IDLE
        if self._current_state == AssistantState.OFFLINE and target != AssistantState.IDLE:
            raise StateTransitionError(
                f"Cannot transition from OFFLINE to {target.value}. Turn the assistant ON first."
            )

        old = self._current_state
        self._previous_state = old
        self._current_state = target

        if target == AssistantState.OFFLINE and self._transient_timer.isActive():
            self._transient_timer.stop()

        # Default human-readable messages per state
        default_msgs = {
            AssistantState.OFFLINE: "Assistant is OFF.",
            AssistantState.IDLE: "Ready and waiting.",
            AssistantState.WAKE_DETECTED: "Wake phrase recognized!",
            AssistantState.LISTENING: "Listening...",
            AssistantState.TRANSCRIBING: "Transcribing speech...",
            AssistantState.THINKING: "Thinking...",
            AssistantState.VALIDATING: "Validating action security...",
            AssistantState.WORKING: "Executing approved action...",
            AssistantState.SPEAKING: "Responding...",
            AssistantState.SUCCESS: "Action completed successfully.",
            AssistantState.ERROR: "An error occurred.",
            AssistantState.BLOCKED: "Action blocked by security policy.",
        }

        self._status_message = message or default_msgs.get(target, target.value)

        # Handle transient states auto-reset to IDLE
        if target in (AssistantState.SUCCESS, AssistantState.ERROR, AssistantState.BLOCKED):
            self._transient_timer.start(3500)
        else:
            if self._transient_timer.isActive():
                self._transient_timer.stop()

        self.state_changed.emit(target, old)
        self.status_message_changed.emit(self._status_message)
        return True

    def trigger_success_feedback(self, msg: str = "Success!") -> None:
        """Utility for visual feedback during successful operations."""
        if self.is_online:
            self.transition_to(AssistantState.SUCCESS, msg)

    def trigger_error_feedback(self, msg: str = "Error occurred.") -> None:
        """Utility for visual feedback during failure states."""
        if self.is_online:
            self.transition_to(AssistantState.ERROR, msg)

    def _handle_transient_timeout(self) -> None:
        """Returns to IDLE after a transient SUCCESS/ERROR feedback state expires."""
        if self.is_online and self._current_state in (
            AssistantState.SUCCESS, AssistantState.ERROR, AssistantState.BLOCKED
        ):
            self.transition_to(AssistantState.IDLE, "Ready.")
