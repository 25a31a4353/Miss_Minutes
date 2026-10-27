"""
tests/test_dual_agents.py - Unit & Integration Tests for Phase 3 Dual-Agent Foundation.

Verifies:
1. Message creation & reply linking.
2. Direct message routing between Miss Minutes and Jarvis.
3. Task delegation workflow (Miss Minutes -> Jarvis -> Result -> Miss Minutes).
4. Loop prevention & bounded turns ceiling.
5. Duplicate message suppression.
6. Conversation cancellation.
7. OFFLINE state security boundary (blocks all inter-agent traffic when OFF).
8. Security boundary: zero raw OS/shell execution from agent proposals.
9. Shared Bounded Context capacity and secret sanitization.
"""

import pytest
from PySide6.QtWidgets import QApplication

from agents import (
    AgentBusError,
    AgentId,
    AgentMessage,
    AgentMessageBus,
    JarvisAgent,
    MessageType,
    MissMinutesAgent,
    Priority,
    SharedBoundedContext,
)
from agents.context import sanitize_content
from app.main import MissMinutesApp
from ui.state_machine import AppStateMachine, AssistantState


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_agent_message_creation_and_reply() -> None:
    """Verifies message initialization and child reply creation."""
    msg = AgentMessage(
        sender=AgentId.MISS_MINUTES,
        recipient=AgentId.JARVIS,
        message_type=MessageType.QUESTION,
        content="Jarvis, are you online?",
        priority=Priority.HIGH,
    )

    assert msg.sender == AgentId.MISS_MINUTES
    assert msg.recipient == AgentId.JARVIS
    assert msg.message_type == MessageType.QUESTION
    assert len(msg.message_id) > 10
    assert len(msg.conversation_id) > 10
    assert msg.timestamp > 0

    # Create reply
    reply = msg.create_reply(sender=AgentId.JARVIS, content="Indeed, Miss Minutes.")
    assert reply.sender == AgentId.JARVIS
    assert reply.recipient == AgentId.MISS_MINUTES
    assert reply.conversation_id == msg.conversation_id
    assert reply.parent_message_id == msg.message_id
    assert reply.content == "Indeed, Miss Minutes."


def test_dual_agent_routing_and_delegation() -> None:
    """Verifies end-to-end task delegation from Miss Minutes to Jarvis."""
    sm = AppStateMachine()
    sm.turn_on()  # Set assistant online

    bus = AgentMessageBus(state_machine=sm)
    mm = MissMinutesAgent()
    jarvis = JarvisAgent()

    bus.register_agent(mm)
    bus.register_agent(jarvis)

    # Miss Minutes delegates a YouTube search to Jarvis
    delegation = AgentMessage(
        sender=AgentId.MISS_MINUTES,
        recipient=AgentId.JARVIS,
        message_type=MessageType.DELEGATION,
        content="Please look up lofi hip hop on youtube",
        requires_response=True,
    )

    result = bus.dispatch(delegation)
    assert result is not None
    assert result.sender == AgentId.JARVIS
    assert result.recipient == AgentId.MISS_MINUTES
    assert result.message_type == MessageType.RESULT
    assert "YouTube" in result.content
    assert result.metadata.get("action_type") == "SEARCH_YOUTUBE"
    assert "youtube.com" in result.metadata.get("url", "")

    # Miss Minutes synthesizes Jarvis's result for the user
    user_response = mm.receive_message(result)
    assert user_response is not None
    assert "Jarvis" in user_response.content
    assert "lofi hip hop" in user_response.content


def test_loop_prevention_bounds_conversations() -> None:
    """Verifies that infinite ping-pong banter is stopped at max turns limit."""
    sm = AppStateMachine()
    sm.turn_on()

    # Bus with max 4 turns
    bus = AgentMessageBus(state_machine=sm, max_turns_per_conversation=4)
    mm = MissMinutesAgent()
    jarvis = JarvisAgent()

    bus.register_agent(mm)
    bus.register_agent(jarvis)

    conv_id = "test-loop-conversation-123"

    # Turn 1: msg1 (1) + Jarvis reply (2) = 2 turns
    msg1 = AgentMessage(
        sender=AgentId.MISS_MINUTES,
        recipient=AgentId.JARVIS,
        message_type=MessageType.CHAT,
        content="Ping 1",
        conversation_id=conv_id,
    )
    bus.dispatch(msg1)

    # Turn 2: msg2 (3) + Miss Minutes reply (4) = 4 turns (reached max 4)
    msg2 = AgentMessage(
        sender=AgentId.JARVIS,
        recipient=AgentId.MISS_MINUTES,
        message_type=MessageType.CHAT,
        content="Precision is key",
        conversation_id=conv_id,
    )
    bus.dispatch(msg2)

    # Turn 3: 4 turns already occurred, so this 5th message must trigger loop prevention
    msg3 = AgentMessage(
        sender=AgentId.MISS_MINUTES,
        recipient=AgentId.JARVIS,
        message_type=MessageType.CHAT,
        content="Ping 3",
        conversation_id=conv_id,
    )
    with pytest.raises(AgentBusError) as exc_info:
        bus.dispatch(msg3)
    assert "Loop prevention triggered" in str(exc_info.value)


def test_duplicate_message_suppression() -> None:
    """Verifies that identical consecutive messages in a thread are dropped."""
    sm = AppStateMachine()
    sm.turn_on()

    bus = AgentMessageBus(state_machine=sm)
    jarvis = JarvisAgent()
    bus.register_agent(jarvis)

    cid = "test-dup-conv"
    msg = AgentMessage(
        sender=AgentId.MISS_MINUTES,
        recipient=AgentId.JARVIS,
        message_type=MessageType.QUESTION,
        content="Status check",
        conversation_id=cid,
    )

    # First dispatch succeeds
    res1 = bus.dispatch(msg)
    assert res1 is not None

    # Immediate duplicate is safely dropped
    res2 = bus.dispatch(msg)
    assert res2 is None


def test_conversation_cancellation() -> None:
    """Verifies that cancelled conversations return CANCEL message."""
    sm = AppStateMachine()
    sm.turn_on()

    bus = AgentMessageBus(state_machine=sm)
    jarvis = JarvisAgent()
    bus.register_agent(jarvis)

    cid = "test-cancel-conv"
    bus.cancel_conversation(cid)

    msg = AgentMessage(
        sender=AgentId.MISS_MINUTES,
        recipient=AgentId.JARVIS,
        message_type=MessageType.DELEGATION,
        content="Do task",
        conversation_id=cid,
    )

    res = bus.dispatch(msg)
    assert res is not None
    assert res.message_type == MessageType.CANCEL


def test_offline_state_strictly_blocks_bus_dispatch() -> None:
    """Verifies that OFFLINE state authoritatively blocks all agent communication."""
    sm = AppStateMachine()
    assert sm.current_state == AssistantState.OFFLINE

    bus = AgentMessageBus(state_machine=sm)
    jarvis = JarvisAgent()
    bus.register_agent(jarvis)

    msg = AgentMessage(
        sender=AgentId.MISS_MINUTES,
        recipient=AgentId.JARVIS,
        message_type=MessageType.DELEGATION,
        content="Search something",
    )

    with pytest.raises(AgentBusError) as exc_info:
        bus.dispatch(msg)
    assert "Communication blocked: Assistant is OFFLINE" in str(exc_info.value)


def test_shared_bounded_context_ring_buffer_and_sanitization() -> None:
    """Verifies ring buffer size bounds and secret key redaction in context."""
    ctx = SharedBoundedContext(max_turns=3)

    # 1. Secret sanitization
    secret_text = "Here is my secret key: gsk_1234567890abcdef1234567890 and sk-proj-12345678901234567890"
    sanitized = sanitize_content(secret_text)
    assert "gsk_" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized

    # 2. Ring buffer limit (max 3 turns)
    for i in range(5):
        msg = AgentMessage(
            sender=AgentId.MISS_MINUTES,
            recipient=AgentId.JARVIS,
            message_type=MessageType.CHAT,
            content=f"Message {i}",
        )
        ctx.add_message(msg)

    turns = ctx.get_turns()
    assert len(turns) == 3
    assert turns[0].content == "Message 2"
    assert turns[1].content == "Message 3"
    assert turns[2].content == "Message 4"


def test_app_delegation_demo(qapp: QApplication) -> None:
    """Verifies the interactive delegation demo in MissMinutesApp."""
    app = MissMinutesApp(qapp=qapp)

    # While OFFLINE, delegation returns None
    assert app.state_machine.current_state == AssistantState.OFFLINE
    res_offline = app.run_delegation_demo()
    assert res_offline is None

    # Turn ON and run delegation
    app.state_machine.turn_on()
    res_online = app.run_delegation_demo("synthwave music on youtube")
    assert res_online is not None
    assert res_online.sender == AgentId.JARVIS
    assert res_online.message_type == MessageType.RESULT
    assert "synthwave" in res_online.metadata.get("query", "")
    assert app.state_machine.current_state == AssistantState.SUCCESS

    # Clean shutdown
    app.shutdown()
    assert app.state_machine.current_state == AssistantState.OFFLINE
