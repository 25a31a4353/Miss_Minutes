"""
agents/base.py - Abstract Base Agent Interface.

Defines the contract implemented by both Miss Minutes and Jarvis.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from agents.message import AgentId, AgentMessage
from agents.personalities import AgentPersonality


class Agent(ABC):
    """
    Abstract interface for AI peer companions.
    """

    def __init__(self, personality: AgentPersonality, capabilities: List[str]) -> None:
        self._personality = personality
        self._capabilities = list(capabilities)

    @property
    def agent_id(self) -> AgentId:
        return self._personality.agent_id

    @property
    def name(self) -> str:
        return self._personality.name

    @property
    def gender(self) -> str:
        return self._personality.gender

    @property
    def personality(self) -> AgentPersonality:
        return self._personality

    @property
    def capabilities(self) -> List[str]:
        return list(self._capabilities)

    @abstractmethod
    def receive_message(
        self,
        message: AgentMessage,
        context: Optional[Any] = None,
    ) -> Optional[AgentMessage]:
        """
        Receives and processes a message from the message bus, optionally returning a reply.
        """
        pass

    @abstractmethod
    def can_handle(self, task_description: str) -> bool:
        """
        Evaluates whether this agent possesses the capability or domain specialization
        to handle the given task.
        """
        pass
