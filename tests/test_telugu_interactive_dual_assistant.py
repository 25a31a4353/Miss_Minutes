"""
tests/test_telugu_interactive_dual_assistant.py - Verification of Telugu Comprehension,
Turn-Taking Dialogue, WhatsApp/Chrome Actions, Hands-Free Listening, and Screen Research.
"""

from __future__ import annotations

import pytest

from actions.apps import APPROVED_APPLICATIONS, resolve_approved_app
from actions.schemas import CapabilityRequest, CapabilityType
from actions.windows_executor import WindowsActionExecutor
from app.pipeline import CapabilityPipeline
from intents.parser import IntentParser
from intents.schema import IntentType, LanguageCode
from voice.listener import ContinuousVoiceListener
from voice.service import VoiceService
from voice.stt import MockSTTProvider
from voice.tts import MockTTSProvider


def test_telugu_intent_parsing_and_language_detection():
    """Verifies that modern Telugu and Telugu-English code-switched commands are accurately parsed."""
    parser = IntentParser()

    # 1. Chrome open command in Telugu
    res_chrome = parser.parse("Chrome open cheyyi")
    assert res_chrome.intent == IntentType.OPEN_APP
    assert res_chrome.entities.app_name == "Google Chrome"

    # 2. WhatsApp open command in Telugu
    res_wa = parser.parse("WhatsApp open cheyyi")
    assert res_wa.intent == IntentType.OPEN_APP
    assert res_wa.entities.app_name == "WhatsApp"

    # 3. Screen reading command in Telugu
    res_screen = parser.parse("Screen meedha emundi choodu")
    assert res_screen.intent == IntentType.READ_SCREEN

    # 4. Quiet / Standby command in Telugu
    res_quiet = parser.parse("Silent ga undu")
    assert res_quiet.intent == IntentType.QUIET_STANDBY

    # 5. Question in Telugu
    res_q = parser.parse("Quantum computing ante enti?")
    assert res_q.intent in (IntentType.QUESTION, IntentType.RESEARCH_EXPLAIN)


def test_turn_taking_dialogue_synthesis():
    """Verifies that Miss Minutes and Jarvis produce paired turn-taking dialogue in Modern Telugu + English."""
    pipeline = CapabilityPipeline()

    # Chat greeting flow
    res = pipeline.execute_pipeline("Namaskaram", is_online=True)
    assert res.success is True
    assert "Miss Minutes" in res.miss_minutes_response
    assert "Jarvis" in res.jarvis_response or len(res.jarvis_response) > 5

    # WhatsApp launch flow
    res_wa = pipeline.execute_pipeline("WhatsApp open cheyyi", is_online=True)
    assert res_wa.success is True
    assert "WhatsApp" in res_wa.miss_minutes_response
    assert "WhatsApp" in res_wa.jarvis_response


def test_whatsapp_resolution_and_fallback():
    """Verifies WhatsApp is allowlisted with desktop protocol and web fallback."""
    wa_desc = resolve_approved_app("whatsapp")
    assert wa_desc is not None
    assert wa_desc["canonical_name"] == "WhatsApp"
    assert wa_desc["web_fallback"] == "https://web.whatsapp.com"

    # Test short alias
    wa_short = resolve_approved_app("wa")
    assert wa_short is not None
    assert wa_short["canonical_name"] == "WhatsApp"


def test_screen_reader_and_research_service():
    """Verifies screen reading and rapid research execution in simulated mode."""
    executor = WindowsActionExecutor(allow_real_execution=False)

    req_screen = CapabilityRequest(capability=CapabilityType.READ_SCREEN)
    res_screen = executor.execute(req_screen)
    assert res_screen.success is True
    assert "action" in res_screen.output

    req_res = CapabilityRequest(capability=CapabilityType.RESEARCH_EXPLAIN, query="Artificial Intelligence")
    res_res = executor.execute(req_res)
    assert res_res.success is True
    assert "summary" in res_res.output


def test_continuous_listener_quiet_mode():
    """Verifies ContinuousVoiceListener quiet mode flags."""
    listener = ContinuousVoiceListener()
    assert listener.is_quiet is False
    listener.set_quiet(True)
    assert listener.is_quiet is True
    listener.set_quiet(False)
    assert listener.is_quiet is False
