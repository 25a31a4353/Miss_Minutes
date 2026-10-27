"""
tests/test_single_jarvis_correction.py - Strict Single Jarvis Architecture Verification.

Verifies the mandatory architecture correction:
COUNT(JARVIS_IMPLEMENTATIONS) = 1.
The existing Jarvis codebase is the single authoritative implementation.
Covers:
- Test 1: Miss Minutes can communicate with the existing Jarvis.
- Test 2: The existing Jarvis can receive an AgentMessage.
- Test 3: The existing Jarvis can return a structured capability proposal.
- Test 4: Jarvis actions pass through security validation.
- Test 5: No second Jarvis implementation is instantiated.
- Test 6: OFFLINE prevents Jarvis action execution.
- Test 7: Existing Jarvis functionality that is retained remains functional.
"""

from __future__ import annotations

import inspect
import pytest

import jarvis
from jarvis import Jarvis, get_jarvis
import jarvis_actions
import jarvis_brain
import jarvis_market
import jarvis_voice

from agents.base import Agent
from agents.bus import AgentMessageBus, AgentBusError
from agents.message import AgentId, AgentMessage, MessageType
from agents.miss_minutes_agent import MissMinutesAgent
from ui.state_machine import AppStateMachine, AssistantState
from actions.schemas import CapabilityRequest, CapabilityType
from security.permissions import SecurityDecision, SecurityValidationResult
from security.validator import SecurityValidator


# ============================================================================
# TEST 1: Miss Minutes can communicate with the existing Jarvis
# ============================================================================
def test_miss_minutes_communicates_with_existing_jarvis() -> None:
    """Verifies bidirectional communication between Miss Minutes and existing Jarvis."""
    sm = AppStateMachine()
    sm.turn_on()
    bus = AgentMessageBus(state_machine=sm)

    miss_minutes = MissMinutesAgent()
    jarvis_inst = Jarvis()

    bus.register_agent(miss_minutes)
    bus.register_agent(jarvis_inst)

    # 1. Miss Minutes sends a chat message to existing Jarvis
    msg = AgentMessage(
        sender=AgentId.MISS_MINUTES,
        recipient=AgentId.JARVIS,
        message_type=MessageType.CHAT,
        content="You're quite the smart clock co-pilot, aren't ya?",
        requires_response=True,
    )
    reply = bus.dispatch(msg)

    assert reply is not None
    assert reply.sender == AgentId.JARVIS
    assert reply.recipient == AgentId.MISS_MINUTES
    assert "Precision is rarely an accident" in reply.content or "doing what is required" in reply.content


# ============================================================================
# TEST 2: The existing Jarvis can receive an AgentMessage
# ============================================================================
def test_existing_jarvis_receives_agent_message() -> None:
    """Verifies that existing Jarvis handles direct AgentMessage types."""
    jarvis_inst = Jarvis()
    assert isinstance(jarvis_inst, Agent)
    assert jarvis_inst.agent_id == AgentId.JARVIS

    # Direct Question
    q_msg = AgentMessage(
        sender=AgentId.USER,
        recipient=AgentId.JARVIS,
        message_type=MessageType.QUESTION,
        content="What is the system diagnostics status?",
        requires_response=True,
    )
    reply = jarvis_inst.receive_message(q_msg)
    assert reply is not None
    assert reply.message_type == MessageType.RESULT
    assert "zero anomalies detected" in reply.content.lower() or "systems functioning" in reply.content.lower()


# ============================================================================
# TEST 3: The existing Jarvis can return a structured capability proposal
# ============================================================================
def test_existing_jarvis_returns_structured_capability_proposal() -> None:
    """Verifies that existing Jarvis translates delegation into a typed capability proposal."""
    jarvis_inst = Jarvis()

    delegation = AgentMessage(
        sender=AgentId.MISS_MINUTES,
        recipient=AgentId.JARVIS,
        message_type=MessageType.DELEGATION,
        content="Could you play AR Rahman songs on YouTube for our friend?",
        metadata={"query": "AR Rahman songs", "action_hint": "SEARCH_YOUTUBE"},
        requires_response=True,
    )

    reply = jarvis_inst.receive_message(delegation)
    assert reply is not None
    assert reply.message_type == MessageType.RESULT
    assert "capability_request" in reply.metadata

    cap_dict = reply.metadata["capability_request"]
    assert cap_dict["capability"] == CapabilityType.PLAY_YOUTUBE
    assert "AR Rahman" in cap_dict["query"]
    assert reply.metadata["security_decision"] == "ALLOW"


# ============================================================================
# TEST 4: Jarvis actions pass through security validation
# ============================================================================
def test_jarvis_actions_pass_through_security_validation() -> None:
    """Verifies that all actions proposed or executed by Jarvis are security validated."""
    # 1. Clean allowlisted action
    clean_req = CapabilityRequest(
        capability=CapabilityType.SEARCH_WEB,
        query="quantum computing architecture",
        requested_by="jarvis",
    )
    clean_res = jarvis_actions.execute_action(clean_req, is_online=True)
    assert clean_res.success is True
    assert clean_res.simulated is True

    # 2. Malicious shell injection attempt inside query
    bad_req = CapabilityRequest(
        capability=CapabilityType.SEARCH_WEB,
        query="powershell -Command Remove-Item C:\\ -Recurse",
        requested_by="jarvis",
    )
    bad_res = jarvis_actions.execute_action(bad_req, is_online=True)
    assert bad_res.success is False
    assert "Security gate blocked action" in (bad_res.error_message or "")


# ============================================================================
# TEST 5: No second Jarvis implementation is instantiated
# ============================================================================
def test_no_second_jarvis_implementation() -> None:
    """
    CRITICAL ARCHITECTURAL CONTRACT:
    COUNT(JARVIS_IMPLEMENTATIONS) = 1.
    Verifies that 'agents.jarvis_agent.JarvisAgent' and 'jarvis.Jarvis'
    refer to the EXACT SAME class and module.
    """
    from agents.jarvis_agent import JarvisAgent as LegacyImport
    from agents import JarvisAgent as PackageImport
    from agents import Jarvis as AgentPackageJarvis

    # 1. Identity checks: all aliases resolve to the single authoritative jarvis.Jarvis
    assert LegacyImport is Jarvis
    assert PackageImport is Jarvis
    assert AgentPackageJarvis is Jarvis

    # 2. Source file location check: class definition lives in jarvis.py
    source_file = inspect.getsourcefile(Jarvis)
    assert source_file is not None
    assert source_file.endswith("jarvis.py")

    # 3. get_jarvis() returns the singleton instance
    inst1 = get_jarvis()
    inst2 = get_jarvis()
    assert inst1 is inst2
    assert isinstance(inst1, Jarvis)


# ============================================================================
# TEST 6: OFFLINE prevents Jarvis action execution
# ============================================================================
def test_offline_prevents_jarvis_action_execution() -> None:
    """Verifies that when assistant is OFFLINE, Jarvis actions are completely blocked."""
    # A. In jarvis_actions.py
    req = CapabilityRequest(capability=CapabilityType.GET_TIME, requested_by="jarvis")
    offline_res = jarvis_actions.execute_action(req, is_online=False)
    assert offline_res.success is False
    assert "OFFLINE" in (offline_res.error_message or "")

    # B. In jarvis_brain.py
    brain_res = jarvis_brain.think("What is the time?", is_online=False)
    assert "OFFLINE" in brain_res

    # C. In jarvis_voice.py
    voice_res = jarvis_voice.speak("Hello", is_online=False)
    assert voice_res is None


# ============================================================================
# TEST 7: Existing Jarvis functionality that is retained remains functional
# ============================================================================
def test_retained_existing_jarvis_functionality() -> None:
    """Verifies that original market, aliases, and brain concepts operate seamlessly."""
    # 1. Market intelligence retained
    assert "^NSEI" in jarvis_market.DEFAULT_TICKERS
    assert "Nifty 50" == jarvis_market.DEFAULT_TICKERS["^NSEI"]
    watchlist = jarvis_market.get_market_watchlist()
    assert isinstance(watchlist, list)

    # 2. Site and alias mappings retained in jarvis_actions
    assert "youtube" in jarvis_actions.SITES
    assert "vs code" in jarvis_actions.ALIASES
    assert jarvis_actions.find_app("chrome") == "Google Chrome"

    # 3. Mail briefing retained
    brief = jarvis_actions.get_mail_brief()
    assert "unread priority emails" in brief

    # 4. Deterministic try_action retained and secured
    time_reply = jarvis_actions.try_action("what time is it", is_online=True)
    assert time_reply is not None
    assert "time" in time_reply.lower() or ":" in time_reply
