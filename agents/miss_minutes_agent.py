"""
agents/miss_minutes_agent.py - Miss Minutes Companion Agent.

Front-of-house desktop companion:
- Warm, witty, playful, curious, and expressive.
- Evaluates user intents and seamlessly delegates technical tasks to Jarvis.
- Translates technical results from Jarvis into friendly, human-accessible summaries.
- Upholds strict security standards and respects the authoritative OFFLINE boundary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.base import Agent
from agents.context import SharedBoundedContext
from agents.message import AgentId, AgentMessage, MessageType
from agents.personalities import MISS_MINUTES_PERSONALITY
from ai.provider import AIProvider, ModelConfig
from ai.prompts import MISS_MINUTES_SYSTEM_PROMPT


class MissMinutesAgent(Agent):
    """
    Miss Minutes primary desktop companion agent.
    """

    def __init__(self, ai_provider: Optional[AIProvider] = None) -> None:
        capabilities = [
            "desktop_interaction",
            "conversational_rapport",
            "task_delegation_coordination",
            "user_intent_parsing",
            "visual_state_expression",
            "multilingual_dialogue",
        ]
        super().__init__(MISS_MINUTES_PERSONALITY, capabilities)
        self._provider = ai_provider

    def set_ai_provider(self, provider: AIProvider) -> None:
        """Sets or updates the active AI intelligence provider."""
        self._provider = provider

    def can_handle(self, task_description: str) -> bool:
        """Miss Minutes handles user engagement, general inquiries, and orchestration."""
        return True

    def receive_message(
        self,
        message: AgentMessage,
        context: Optional[SharedBoundedContext] = None,
    ) -> Optional[AgentMessage]:
        """Processes incoming messages from Jarvis or the User."""
        m_type = message.message_type
        # 1. Handle Direct User Messages
        if message.sender == AgentId.USER:
            return self._handle_user_message(message, context=context)

        # 2. Handle Technical Results returned by Jarvis
        if m_type == MessageType.RESULT:
            return self._handle_jarvis_result(message)

        # 3. Handle Banter / Friendly Chat from Jarvis
        if m_type == MessageType.CHAT:
            return self._handle_jarvis_chat(message)

        # 4. Handle Question from Jarvis
        if m_type == MessageType.QUESTION:
            return message.create_reply(
                sender=self.agent_id,
                content="Looking good on my end, Jarvis! Proceed as planned.",
                message_type=MessageType.RESULT,
            )

        return None

    def _handle_jarvis_result(self, message: AgentMessage) -> AgentMessage:
        """Synthesizes Jarvis's technical output into a warm user response."""
        meta = message.metadata
        action_type = meta.get("action_type")

        if action_type == "SEARCH_YOUTUBE":
            query = meta.get("query", "")
            return message.create_reply(
                sender=self.agent_id,
                content=f"Jarvis got that YouTube music search ready for '{query}', honey!",
                message_type=MessageType.CHAT,
            )

        if action_type == "SEARCH_WEB":
            query = meta.get("query", "")
            return message.create_reply(
                sender=self.agent_id,
                content=f"Search is all prepped for '{query}'! Jarvis never misses a beat.",
                message_type=MessageType.CHAT,
            )

        if action_type == "OPEN_APPROVED_APP":
            app = meta.get("target_app", "")
            return message.create_reply(
                sender=self.agent_id,
                content=f"Jarvis confirmed '{app}' is ready to launch on your computer, sugar!",
                message_type=MessageType.CHAT,
            )

        # Default synthesis
        return message.create_reply(
            sender=self.agent_id,
            content=f"Jarvis finished that up: {message.content}",
            message_type=MessageType.CHAT,
        )

    def _handle_jarvis_chat(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Playfully responds to Jarvis's dry remarks."""
        q = message.content.lower()
        if "precision" in q or "nominal" in q:
            return message.create_reply(
                sender=self.agent_id,
                content="Show-off! But that's why we make such a good team.",
                message_type=MessageType.CHAT,
            )
        return None

    def _handle_user_message(
        self,
        message: AgentMessage,
        context: Optional[SharedBoundedContext] = None,
    ) -> AgentMessage:
        """Handles direct user requests and decides whether to delegate to Jarvis."""
        q = message.content.lower()

        # If user is asking for technical / media / app actions, delegate to Jarvis
        if any(w in q for w in ("youtube", "search", "google", "stock", "market", "open", "launch")):
            return message.create_reply(
                sender=self.agent_id,
                content="Hold on just a second, sugar! I'm asking Jarvis to verify the technical details for you.",
                message_type=MessageType.NOTIFICATION,
                metadata={"should_delegate": True, "target_agent": AgentId.JARVIS.value},
            )

        # Conversational / General inquiry: Use AI provider with multi-turn memory
        if self._provider and self._provider.is_available():
            cfg = ModelConfig(
                system_instruction=MISS_MINUTES_SYSTEM_PROMPT,
                temperature=0.7,
                max_tokens=400,
            )

            # Build multi-turn message history from context
            history_msgs: List[dict[str, str]] = []
            if context:
                recent_turns = context.get_turns(limit=context.max_turns)
                for turn in recent_turns:
                    role = "user" if turn.sender == AgentId.USER else "assistant"
                    history_msgs.append({"role": role, "content": turn.content})

            # Append current user utterance if not already at end of history
            if not history_msgs or history_msgs[-1].get("content") != message.content:
                history_msgs.append({"role": "user", "content": message.content})

            try:
                resp = self._provider.generate_chat_response(history_msgs, config=cfg)
                return message.create_reply(
                    sender=self.agent_id,
                    content=resp.content.strip(),
                    message_type=MessageType.CHAT,
                )
            except Exception:
                # Controlled local fallback
                pass

        return message.create_reply(
            sender=self.agent_id,
            content=f"Well hey there! I heard you say: '{message.content}'. What would you like to do next?",
            message_type=MessageType.CHAT,
        )
