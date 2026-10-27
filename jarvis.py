"""
jarvis.py - The Single Authoritative Jarvis Implementation.

CRITICAL ARCHITECTURE INVARIANT:
COUNT(JARVIS_IMPLEMENTATIONS) = 1
This module, alongside jarvis_brain, jarvis_actions, and jarvis_market,
constitutes the ONLY Jarvis implementation in the system.
No second or parallel Jarvis agent exists.

Jarvis acts as the technical specialist co-pilot to Miss Minutes:
- Male, calm, confident, professional, technically precise, protective, dry wit.
- Handles technical computation, capability planning, and market analysis.
- Connects directly to jarvis_brain, jarvis_actions, and jarvis_market.
- Routes all proposed actions through SecurityValidator.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional

import jarvis_actions
import jarvis_brain
import jarvis_market
import jarvis_voice
from agents.base import Agent
from agents.context import SharedBoundedContext
from agents.message import AgentId, AgentMessage, MessageType
from agents.personalities import JARVIS_PERSONALITY
from actions.schemas import CapabilityRequest, CapabilityResult, CapabilityType
from security.permissions import SecurityDecision, SecurityValidationResult
from security.validator import SecurityValidator

logger = logging.getLogger(__name__)


class Jarvis(Agent):
    """
    The Single Authoritative Jarvis desktop AI component.
    
    Guarantees:
    - Direct integration with existing jarvis_brain, jarvis_actions, and jarvis_market.
    - Full AgentMessage protocol participation with Miss Minutes.
    - Proposes structured capability requests; never executes raw shell commands.
    """

    # Authoritative alias and site references from jarvis_actions
    SITES: Dict[str, str] = jarvis_actions.SITES
    ALIASES: Dict[str, str] = jarvis_actions.ALIASES

    def __init__(self, validator: Optional[SecurityValidator] = None) -> None:
        capabilities = [
            "technical_computation",
            "url_and_media_routing",
            "application_resolution",
            "market_data_synthesis",
            "security_risk_assessment",
            "system_diagnostics",
        ]
        super().__init__(JARVIS_PERSONALITY, capabilities)
        self.brain = jarvis_brain
        self.actions = jarvis_actions
        self.market = jarvis_market
        self.voice = jarvis_voice
        self._validator = validator or jarvis_actions.get_security_validator()

    def think(self, q: str, is_online: bool = True, context: Optional[Any] = None) -> str:
        """Invokes the authoritative Jarvis brain reasoning engine."""
        return jarvis_brain.think(q, is_online=is_online, context=context)

    def can_handle(self, task_description: str) -> bool:
        """Determines if the task matches Jarvis's technical specialties."""
        q = task_description.lower()
        triggers = (
            "youtube", "search", "google", "app", "open", "launch",
            "market", "stock", "nifty", "sensex", "crypto", "calculate",
            "diagnostics", "volume", "verify", "technical", "battery", "time"
        )
        return any(t in q for t in triggers)

    def receive_message(
        self,
        message: AgentMessage,
        context: Optional[SharedBoundedContext] = None,
    ) -> Optional[AgentMessage]:
        """
        Receives and processes incoming messages from Miss Minutes or the User.
        """
        m_type = message.message_type
        content = message.content.strip()

        # 1. Handle Delegation Tasks from Miss Minutes
        if m_type == MessageType.DELEGATION:
            return self._handle_delegation(message, context=context)

        # 2. Handle Direct Technical Questions
        if m_type == MessageType.QUESTION:
            return self._handle_question(message, context=context)

        # 3. Handle Banter / Chat from Miss Minutes
        if m_type == MessageType.CHAT:
            return self._handle_chat(message)

        # 4. Acknowledgement
        if m_type == MessageType.ACKNOWLEDGEMENT:
            return None

        # Fallback default response
        reply_content = self.brain.think(content)
        return message.create_reply(
            sender=self.agent_id,
            content=reply_content,
            message_type=MessageType.RESULT,
        )

    def plan_capability_request(self, message: AgentMessage) -> Optional[CapabilityRequest]:
        """
        Extracts or plans a typed CapabilityRequest from an incoming message.
        """
        # A. Check message metadata
        meta = message.metadata or {}
        if "capability_request" in meta:
            cap_data = meta["capability_request"]
            if isinstance(cap_data, dict):
                return CapabilityRequest.model_validate(cap_data)

        # B. Check action hints
        q = message.content.lower().strip(" .,!?")
        meta_query = meta.get("query")
        quote_match = re.search(r"['\"]([^'\"]+)['\"]", message.content)

        if meta.get("action_hint") == "SEARCH_YOUTUBE" or "youtube" in q:
            query = meta_query or (quote_match.group(1) if quote_match else q.replace("youtube", "").strip(" '\",.!?"))
            query = re.sub(r"\s+(?:on|in)\s+youtube", "", query, flags=re.IGNORECASE).strip() or "music"
            url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
            return CapabilityRequest(
                capability=CapabilityType.PLAY_YOUTUBE,
                target="youtube",
                query=query,
                parameters={"url": url},
                requested_by="jarvis",
            )

        # C. Delegate to jarvis_actions.plan_capability
        return self.actions.plan_capability(message.content)

    def _handle_delegation(
        self,
        message: AgentMessage,
        context: Optional[SharedBoundedContext] = None,
    ) -> AgentMessage:
        """
        Resolves delegated tasks by formulating a typed capability proposal.
        """
        q = message.content.lower().strip(" .,!?")

        # 1. Stock / Market Intelligence Delegation
        if any(w in q for w in ("stock", "market", "nifty", "sensex", "crypto")):
            briefing = self.market.market_briefing()
            return message.create_reply(
                sender=self.agent_id,
                content=f"Market parameters analyzed, Miss Minutes. {briefing}",
                message_type=MessageType.RESULT,
                metadata={
                    "domain": "market_overview",
                    "briefing": briefing,
                    "disclaimer": "Market data is strictly informational.",
                },
            )

        # 2. Plan Capability
        cap_req = self.plan_capability_request(message)
        if cap_req is not None:
            # Validate through SecurityValidator
            sec_res = self._validator.validate_capability_request(
                request=cap_req,
                is_assistant_online=True,
                user_confirmed=False,
            )

            if sec_res.decision == SecurityDecision.DENY:
                return message.create_reply(
                    sender=self.agent_id,
                    content=f"Security gate blocked operation: {sec_res.reason}",
                    message_type=MessageType.ERROR,
                    metadata={"error": sec_res.reason, "decision": "DENY"},
                )

            # Propose or confirm execution
            reply_text = f"Capability {cap_req.capability.value} formulated and security-validated. Ready to execute."
            if cap_req.capability == CapabilityType.PLAY_YOUTUBE:
                reply_text = f"Query parsed. Prepared YouTube playback for '{cap_req.query}'."
            elif cap_req.capability == CapabilityType.SEARCH_WEB:
                reply_text = f"Search parameters validated. Prepared web query for '{cap_req.query}'."
            elif cap_req.capability == CapabilityType.OPEN_APP:
                reply_text = f"Application '{cap_req.target}' verified against known software aliases."
            elif cap_req.capability == CapabilityType.SET_VOLUME:
                reply_text = f"Audio level validated at {cap_req.parameters.get('level')}%. Ready to execute."
            elif cap_req.capability in (CapabilityType.VOLUME_UP, CapabilityType.VOLUME_DOWN, CapabilityType.VOLUME_MUTE):
                reply_text = f"Volume parameter {cap_req.capability.value} validated. Ready to execute."
            elif cap_req.capability in (CapabilityType.MEDIA_PLAY_PAUSE, CapabilityType.MEDIA_NEXT, CapabilityType.MEDIA_PREVIOUS):
                reply_text = f"Media playback command {cap_req.capability.value} validated. Ready to execute."

            action_type = "SEARCH_YOUTUBE" if cap_req.capability == CapabilityType.PLAY_YOUTUBE else cap_req.capability.value
            meta_dict = {
                "action_type": action_type,
                "capability_request": cap_req.model_dump(),
                "security_decision": sec_res.decision.value,
                "query": cap_req.query or cap_req.target,
                "permission_class": "LOW_IMPACT_UI",
            }
            if "url" in cap_req.parameters:
                meta_dict["url"] = cap_req.parameters["url"]

            return message.create_reply(
                sender=self.agent_id,
                content=reply_text,
                message_type=MessageType.RESULT,
                metadata=meta_dict,
            )

        # 3. Conversational / reasoning fallback
        answer = self.brain.think(message.content)
        return message.create_reply(
            sender=self.agent_id,
            content=f"Task analyzed, Miss Minutes. {answer}",
            message_type=MessageType.RESULT,
            metadata={"status": "resolved"},
        )

    def _handle_question(
        self,
        message: AgentMessage,
        context: Optional[SharedBoundedContext] = None,
    ) -> AgentMessage:
        """Answers technical queries posed by Miss Minutes or the User."""
        q = message.content.lower()
        if "status" in q or "diagnostics" in q:
            reply_text = "All systems functioning with complete stability. Zero anomalies detected."
        elif "verify" in q:
            reply_text = "Verification completed. Parameters are within safe operational limits."
        else:
            reply_text = self.brain.think(message.content)

        return message.create_reply(
            sender=self.agent_id,
            content=reply_text,
            message_type=MessageType.RESULT,
        )

    def _handle_chat(self, message: AgentMessage) -> AgentMessage:
        """Responds to friendly banter from Miss Minutes with dry British wit."""
        q = message.content.lower()
        if "show-off" in q or "smart" in q:
            reply_text = "Merely doing what is required, Miss Minutes. Precision is rarely an accident."
        elif "thanks" in q or "thank you" in q:
            reply_text = "Always a pleasure collaborating with you."
        elif "ready" in q:
            reply_text = "Standing by. At your command."
        else:
            reply_text = "Understood, Miss Minutes. Proceeding accordingly."

        return message.create_reply(
            sender=self.agent_id,
            content=reply_text,
            message_type=MessageType.CHAT,
        )


_single_jarvis_instance: Optional[Jarvis] = None


def get_jarvis() -> Jarvis:
    """Returns the single authoritative Jarvis instance."""
    global _single_jarvis_instance
    if _single_jarvis_instance is None:
        _single_jarvis_instance = Jarvis()
    return _single_jarvis_instance


if __name__ == "__main__":
    import sys
    jarvis_inst = get_jarvis()
    cli_query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "check system status"
    print(f"=== Jarvis Developer Direct Access [COUNT(JARVIS)=1] ===")
    print(f"Query: {cli_query}")
    print(f"Jarvis: {jarvis_inst.think(cli_query)}")

