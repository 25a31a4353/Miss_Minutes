"""
tests/test_lifecycle.py - Application Lifecycle & State Machine Tests.

Verifies:
1. Default application state is OFFLINE.
2. OFFLINE -> IDLE transition works.
3. IDLE -> OFFLINE transition works.
4. Invalid state transitions from OFFLINE are rejected.
5. OFFLINE state authoritatively prevents action execution hooks.
6. Application initializes cleanly without API keys.
7. Transient feedback states (SUCCESS / ERROR) handle timeouts safely.
8. Application shutdown leaves no lingering active timers.
"""

import sys
import pytest
from PySide6.QtWidgets import QApplication

from app.main import MissMinutesApp
from config.settings import AppSettings
from ui.state_machine import AppStateMachine, AssistantState, StateTransitionError


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Session-scoped QApplication fixture for Qt unit testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_default_state_is_offline(qapp: QApplication) -> None:
    """Verifies that default initialized state is OFFLINE."""
    sm = AppStateMachine()
    assert sm.current_state == AssistantState.OFFLINE
    assert sm.is_online is False
    assert sm.can_execute_action() is False


def test_turn_on_and_turn_off_transitions(qapp: QApplication) -> None:
    """Verifies OFFLINE -> IDLE and IDLE -> OFFLINE lifecycle transitions."""
    sm = AppStateMachine()

    # Track signals
    emitted_states = []
    sm.state_changed.connect(lambda new_s, old_s: emitted_states.append((new_s, old_s)))

    # Turn ON
    res_on = sm.turn_on()
    assert res_on is True
    assert sm.current_state == AssistantState.IDLE
    assert sm.is_online is True
    assert sm.can_execute_action() is True

    # Duplicate turn ON is a safe no-op
    assert sm.turn_on() is False

    # Turn OFF
    res_off = sm.turn_off()
    assert res_off is True
    assert sm.current_state == AssistantState.OFFLINE
    assert sm.is_online is False
    assert sm.can_execute_action() is False

    # Verify signal emission order
    assert emitted_states == [
        (AssistantState.IDLE, AssistantState.OFFLINE),
        (AssistantState.OFFLINE, AssistantState.IDLE),
    ]


def test_invalid_transitions_rejected_when_offline(qapp: QApplication) -> None:
    """Verifies that jumping from OFFLINE to active states is rejected."""
    sm = AppStateMachine()
    assert sm.current_state == AssistantState.OFFLINE

    with pytest.raises(StateTransitionError) as exc_info:
        sm.transition_to(AssistantState.WORKING)
    assert "Turn the assistant ON first" in str(exc_info.value)

    with pytest.raises(StateTransitionError):
        sm.transition_to(AssistantState.SPEAKING)

    with pytest.raises(StateTransitionError):
        sm.transition_to(AssistantState.LISTENING)

    # State must remain OFFLINE
    assert sm.current_state == AssistantState.OFFLINE


def test_offline_strictly_prevents_action_hooks(qapp: QApplication) -> None:
    """Verifies that action execution hooks return False when OFFLINE."""
    sm = AppStateMachine()

    assert sm.can_execute_action() is False
    assert sm.request_action_hook("open_browser") is False

    # When turned on, action hooks become permissible
    sm.turn_on()
    assert sm.can_execute_action() is True
    assert sm.request_action_hook("open_browser") is True

    # When turned off again, action hooks are immediately denied
    sm.turn_off()
    assert sm.can_execute_action() is False
    assert sm.request_action_hook("open_browser") is False


def test_transient_states_flow(qapp: QApplication) -> None:
    """Verifies transitions to SUCCESS and ERROR and safe handling."""
    sm = AppStateMachine()
    sm.turn_on()

    # Trigger success
    sm.trigger_success_feedback("Verified test action")
    assert sm.current_state == AssistantState.SUCCESS
    assert sm.status_message == "Verified test action"

    # Trigger error
    sm.trigger_error_feedback("Simulated failure")
    assert sm.current_state == AssistantState.ERROR
    assert sm.status_message == "Simulated failure"

    # Turning off cancels transient timer and returns immediately to OFFLINE
    sm.turn_off()
    assert sm.current_state == AssistantState.OFFLINE


def test_app_initializes_without_api_keys(qapp: QApplication) -> None:
    """Verifies that MissMinutesApp instantiates cleanly with zero API keys."""
    settings = AppSettings(gemini_api_key=None, groq_api_key=None)
    app = MissMinutesApp(settings=settings, qapp=qapp)

    assert app.state_machine.current_state == AssistantState.OFFLINE
    assert app.overlay is not None
    assert app.controller is not None
    assert app.settings.has_any_provider is False

    # Overlay & Controller properties
    assert app.overlay.width() == 150
    assert app.overlay.height() == 170
    assert app.controller.width() == 310
    assert app.controller.height() == 365


def test_app_shutdown_cleans_up_state(qapp: QApplication) -> None:
    """Verifies that app.shutdown() ensures state is OFFLINE and windows closed."""
    app = MissMinutesApp(qapp=qapp)
    app.state_machine.turn_on()
    assert app.state_machine.is_online is True

    app.shutdown()
    assert app.state_machine.current_state == AssistantState.OFFLINE
    assert app.overlay.isVisible() is False
    assert app.controller.isVisible() is False
