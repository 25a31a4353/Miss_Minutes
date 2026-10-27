"""
agents/bus.py - Authoritative Agent Message Bus.

Guarantees:
- Enforces loop prevention (maximum agent-to-agent turns).
- Enforces duplicate message suppression.
- Enforces OFFLINE gating (blocks communication when assistant is OFFLINE).
- Supports dynamic conversation cancellation.
- Records all exchanges in the audit log and shared bounded context.
"""

from __future__ import annotations

import time
from typing import Dict, Optional, Set

from agents.audit_log import AgentAuditLogger
from agents.base import Agent
from agents.context import SharedBoundedContext
from agents.message import AgentId, AgentMessage, MessageType
from ui.state_machine import AppStateMachine, AssistantState


class AgentBusError(Exception):
    """Raised when message bus delivery violates protocol or safety rules."""
    pass


class AgentMessageBus:
    """
    In-memory message bus routing messages between Miss Minutes, Jarvis, and the User.
    """

    def __init__(
        self,
        state_machine: Optional[AppStateMachine] = None,
        context: Optional[SharedBoundedContext] = None,
        audit_logger: Optional[AgentAuditLogger] = None,
        max_turns_per_conversation: int = 5,
        conversation_timeout_seconds: float = 30.0,
        max_delegation_depth: int = 3,
    ) -> None:
        self._state_machine = state_machine
        self._context = context or SharedBoundedContext(max_turns=10)
        self._logger = audit_logger or AgentAuditLogger()
        self._max_turns = max_turns_per_conversation
        self._timeout_seconds = conversation_timeout_seconds
        self._max_delegation_depth = max_delegation_depth

        self._agents: Dict[AgentId, Agent] = {}
        self._conversation_turns: Dict[str, int] = {}
        self._conversation_timestamps: Dict[str, float] = {}
        self._delegation_depths: Dict[str, int] = {}
        self._last_messages: Dict[str, tuple] = {}
        self._cancelled_conversations: Set[str] = set()

    @property
    def context(self) -> SharedBoundedContext:
        return self._context

    @property
    def audit_logger(self) -> AgentAuditLogger:
        return self._logger

    def register_agent(self, agent: Agent) -> None:
        """Registers an agent with the bus."""
        self._agents[agent.agent_id] = agent

    def get_agent(self, agent_id: AgentId) -> Optional[Agent]:
        """Returns the registered agent instance for an AgentId."""
        return self._agents.get(agent_id)

    def is_offline(self) -> bool:
        """Returns True if the underlying assistant FSM is in the OFFLINE state."""
        if self._state_machine:
            return self._state_machine.current_state == AssistantState.OFFLINE
        return False

    def cancel_conversation(self, conversation_id: str) -> None:
        """Cancels an active conversation, causing any subsequent messages to fail."""
        self._cancelled_conversations.add(conversation_id)

    def dispatch(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Dispatches an AgentMessage through security, loop, and routing filters.
        
        Returns the recipient's reply if generated, or None.
        """
        # 1. OFFLINE Invariant Check: Drop all communication when assistant is OFF
        if self.is_offline():
            raise AgentBusError(
                f"Communication blocked: Assistant is OFFLINE. Cannot deliver message from {message.sender.value}."
            )

        cid = message.conversation_id

        # 2. Check if conversation was explicitly cancelled
        if cid in self._cancelled_conversations:
            return AgentMessage(
                sender=AgentId.MISS_MINUTES,
                recipient=message.sender,
                message_type=MessageType.CANCEL,
                content="Conversation was cancelled.",
                conversation_id=cid,
            )

        # 3. Check for Conversation Timeout
        now = time.time()
        last_time = self._conversation_timestamps.get(cid, now)
        if (now - last_time) > self._timeout_seconds:
            self._cancelled_conversations.add(cid)
            raise AgentBusError(f"Conversation {cid} timed out after {self._timeout_seconds}s.")
        self._conversation_timestamps[cid] = now

        # 4. Turn Count / Loop Prevention Check
        current_turns = self._conversation_turns.get(cid, 0)
        if current_turns >= self._max_turns:
            # Terminate loop
            raise AgentBusError(
                f"Loop prevention triggered: Conversation {cid} reached maximum limit of {self._max_turns} turns."
            )
        self._conversation_turns[cid] = current_turns + 1

        # 4b. Delegation Depth Check
        if message.message_type == MessageType.DELEGATION:
            current_depth = self._delegation_depths.get(cid, 0)
            if current_depth >= self._max_delegation_depth:
                raise AgentBusError(
                    f"Delegation depth limit reached: Conversation {cid} exceeded maximum delegation depth of {self._max_delegation_depth}."
                )
            self._delegation_depths[cid] = current_depth + 1

        # 5. Duplicate Message Suppression
        msg_sig = (message.sender, message.recipient, message.message_type, message.content.strip())
        if self._last_messages.get(cid) == msg_sig:
            # Drop duplicate echo safely
            return None
        self._last_messages[cid] = msg_sig

        # 6. Record to Context & Audit Log
        self._context.add_message(message)
        self._logger.log_message(message)

        # 7. Route to Recipient Agent
        recipient_agent = self._agents.get(message.recipient)
        if not recipient_agent:
            # Unknown recipient
            return AgentMessage(
                sender=message.recipient,
                recipient=message.sender,
                message_type=MessageType.ERROR,
                content=f"Recipient agent {message.recipient.value} is not registered on the bus.",
                conversation_id=cid,
            )

        # Invoke agent processing
        reply = recipient_agent.receive_message(message, self._context)

        # 8. If reply generated, process reply through bus logging
        if reply is not None:
            self._context.add_message(reply)
            self._logger.log_message(reply)
            self._conversation_turns[cid] = self._conversation_turns.get(cid, 0) + 1

        return reply

    def delegate_task(
        self,
        from_agent: AgentId,
        to_agent: AgentId,
        task_instruction: str,
    ) -> Optional[AgentMessage]:
        """
        Convenience method to execute a clean delegation workflow.
        """
        delegation_msg = AgentMessage(
            sender=from_agent,
            recipient=to_agent,
            message_type=MessageType.DELEGATION,
            content=task_instruction,
            requires_response=True,
        )
        return self.dispatch(delegation_msg)
