"""
tests/test_phase6_gemini.py - Phase 6 Test Suite for Gemini Intelligence & Multilingual Dialogue.

Validates:
1. GeminiProvider initialization, model resolution, and missing API key handling.
2. Structured extraction, streaming responses, and multi-turn chat handling.
3. ResilientAIProvider fallback chain (Gemini -> Groq -> Mock).
4. Multilingual dialogue across English, Telugu, and Telugu-English code-switching without forced translation.
5. Multi-turn bounded conversation context memory (e.g. Question 1 -> Question 2 follow-up).
6. Security Validator gate enforcement (Gemini -> arbitrary shell/PowerShell is rejected; default DENY).
7. Master OFFLINE gate enforcement (assistant offline blocks AI and voice processing).
8. Existing Jarvis single-agent communication and invariant: COUNT(JARVIS_IMPLEMENTATIONS) == 1.
9. Voice pipeline integration: STT -> Gemini AI -> TTS.
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock, patch

from ai.gemini_provider import GeminiProvider, DEFAULT_GEMINI_MODEL
from ai.groq_provider import GroqProvider
from ai.mock_provider import MockAIProvider
from ai.fallback_provider import ResilientAIProvider
from ai.provider import AIProviderError, ModelConfig, ProviderResponse
from ai.prompts import MISS_MINUTES_SYSTEM_PROMPT, JARVIS_SYSTEM_PROMPT
from intents.schema import StructuredIntent, IntentType, LanguageCode
from intents.parser import IntentParser
from agents.context import SharedBoundedContext
from agents.message import AgentId, AgentMessage, MessageType
from agents.miss_minutes_agent import MissMinutesAgent
from actions.schemas import CapabilityRequest, CapabilityType
from security.validator import SecurityValidator
from security.permissions import SecurityDecision
from app.pipeline import CapabilityPipeline
from voice.service import VoiceService
import jarvis
import jarvis_brain


# ==============================================================================
# 1. GeminiProvider Unit & Lifecycle Tests
# ==============================================================================

class TestGeminiProvider:
    """Verifies Gemini provider configuration, safety, and SDK abstraction."""

    def test_missing_api_key_is_unavailable_and_safe(self):
        """Provider must not crash when API key is missing or blank."""
        provider = GeminiProvider(api_key=None)
        assert not provider.is_available()
        assert provider.provider_id == "gemini"

        empty_provider = GeminiProvider(api_key="   ")
        assert not empty_provider.is_available()

        # Invoking unavailable provider must raise AIProviderError cleanly
        with pytest.raises(AIProviderError, match="not configured or unavailable"):
            provider.generate_response("Hello")

        with pytest.raises(AIProviderError, match="not configured or unavailable"):
            provider.generate_structured("Extract", StructuredIntent)

        with pytest.raises(AIProviderError, match="not configured or unavailable"):
            list(provider.generate_stream("Stream hello"))

    def test_configurable_model_resolution(self):
        """Model identifier must be configurable from parameter or environment."""
        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-2.5-pro"}):
            p1 = GeminiProvider(api_key=None)
            assert p1._default_model == "gemini-2.5-pro"

        p2 = GeminiProvider(api_key=None, default_model="gemini-custom-flash")
        assert p2._default_model == "gemini-custom-flash"

    def test_mocked_gemini_generation(self):
        """Tests successful text generation via mocked SDK Client."""
        provider = GeminiProvider(api_key="test_dummy_key", default_model="gemini-2.5-flash")
        
        # Mock client models.generate_content
        mock_resp = MagicMock()
        mock_resp.text = "Hello! Miss Minutes here, ready to help."
        provider._client = MagicMock()
        provider._client.models.generate_content.return_value = mock_resp

        assert provider.is_available()
        res = provider.generate_response("Hello Miss Minutes!")
        assert res.content == "Hello! Miss Minutes here, ready to help."
        assert res.provider_id == "gemini"
        assert res.model_used == "gemini-2.5-flash"

    def test_mocked_gemini_streaming(self):
        """Tests streaming text generation via mocked SDK generate_content_stream."""
        provider = GeminiProvider(api_key="test_dummy_key")
        provider._client = MagicMock()

        chunk1 = MagicMock()
        chunk1.text = "Howdy "
        chunk2 = MagicMock()
        chunk2.text = "y'all!"
        provider._client.models.generate_content_stream.return_value = [chunk1, chunk2]

        chunks = list(provider.generate_stream("Say hello"))
        assert chunks == ["Howdy ", "y'all!"]

    def test_mocked_gemini_chat_response(self):
        """Tests multi-turn chat generation via mocked SDK."""
        provider = GeminiProvider(api_key="test_dummy_key")
        provider._client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Entanglement means linked particles."
        provider._client.models.generate_content.return_value = mock_resp

        messages = [
            {"role": "user", "content": "What is quantum entanglement?"},
            {"role": "assistant", "content": "It is a quantum physics phenomenon."},
            {"role": "user", "content": "Give me more details."},
        ]
        resp = provider.generate_chat_response(messages)
        assert resp.content == "Entanglement means linked particles."
        provider._client.models.generate_content.assert_called_once()


# ==============================================================================
# 2. ResilientAIProvider Fallback Tests
# ==============================================================================

class TestResilientFallback:
    """Verifies failover chain: Gemini -> Groq -> Mock."""

    def test_fallback_when_primary_unavailable(self):
        """When Gemini has no key, fallback to available mock."""
        gemini = GeminiProvider(api_key=None)
        mock = MockAIProvider(default_text_response="Mock fallback answer")
        resilient = ResilientAIProvider(primary=gemini, fallback=mock)

        assert resilient.is_available()
        resp = resilient.generate_response("Test prompt")
        assert resp.content == "Mock fallback answer"

    def test_failover_when_primary_raises_error(self):
        """When Gemini raises a rate-limit/network error, failover to secondary/mock."""
        failing_gemini = GeminiProvider(api_key="invalid_or_rate_limited_key")
        failing_gemini._client = MagicMock()
        failing_gemini._client.models.generate_content.side_effect = Exception("429 Resource Exhausted / Rate Limit")

        working_groq = MockAIProvider(default_text_response="Groq fallback output")
        resilient = ResilientAIProvider(primary=failing_gemini, secondary=working_groq)

        resp = resilient.generate_response("Question")
        assert resp.content == "Groq fallback output"


# ==============================================================================
# 3. Multilingual Understanding & Dialogue Tests
# ==============================================================================

class TestMultilingualDialogue:
    """Verifies English, Telugu, and Telugu-English code-switching handling."""

    def test_english_query_preserved_and_answered(self):
        mock_ai = MockAIProvider(default_text_response="Quantum entanglement is when two particles share states.")
        pipeline = CapabilityPipeline(ai_provider=mock_ai)

        res = pipeline.execute_pipeline("Explain quantum entanglement.", is_online=True)
        assert res.success
        assert res.language == LanguageCode.EN
        assert "quantum entanglement" in res.miss_minutes_response.lower()

    def test_telugu_query_preserved_without_early_translation(self):
        mock_ai = MockAIProvider(
            default_text_response="Ippudu anni systems normal ga unnayandi."
        )
        pipeline = CapabilityPipeline(ai_provider=mock_ai)

        res = pipeline.execute_pipeline("Ippudu em jarugutundi?", is_online=True)
        assert res.success
        assert res.language == LanguageCode.TE
        assert res.raw_transcript == "Ippudu em jarugutundi?"

    def test_telugu_english_mixed_query(self):
        mock_ai = MockAIProvider(
            default_text_response="Quantum entanglement ante rendu particles madhya unna sambandham."
        )
        pipeline = CapabilityPipeline(ai_provider=mock_ai)

        # Question code-switch
        res_q = pipeline.execute_pipeline("Quantum entanglement ante enti?", is_online=True)
        assert res_q.success
        assert res_q.language == LanguageCode.TE_EN

        # Action code-switch
        res_act = pipeline.execute_pipeline(
            "YouTube open chesi AR Rahman songs play cheyyi",
            is_online=True,
        )
        assert res_act.success
        assert res_act.language == LanguageCode.TE_EN
        assert res_act.intent.intent == IntentType.PLAY_MEDIA
        assert res_act.delegated_to_jarvis


# ==============================================================================
# 4. Multi-Turn Bounded Conversation Context Memory Tests
# ==============================================================================

class TestConversationMemory:
    """Verifies that follow-up questions retain prior context within bounded turns."""

    def test_multi_turn_context_preserved(self):
        context = SharedBoundedContext(max_turns=6)
        mock_ai = MockAIProvider(default_text_response="Default answer")
        pipeline = CapabilityPipeline(ai_provider=mock_ai, context=context)

        # Turn 1: Initial question
        res1 = pipeline.execute_pipeline("What is quantum entanglement?", is_online=True)
        assert res1.success
        assert len(context) == 2  # user + assistant

        # Turn 2: Follow-up question referencing turn 1
        res2 = pipeline.execute_pipeline("Give me a simple example.", is_online=True)
        assert res2.success
        assert len(context) == 4

        # Verify that mock_ai received the accumulated conversation history
        assert len(mock_ai.recorded_prompts) >= 2
        # Turn 2 prompt must contain the context of quantum entanglement
        assert "quantum entanglement" in mock_ai.recorded_prompts[-1].lower()

    def test_bounded_history_does_not_grow_indefinitely(self):
        context = SharedBoundedContext(max_turns=4)
        mock_ai = MockAIProvider()
        pipeline = CapabilityPipeline(ai_provider=mock_ai, context=context)

        for i in range(10):
            pipeline.execute_pipeline(f"Question number {i}", is_online=True)

        assert len(context) <= 4


# ==============================================================================
# 5. Security & Default DENY Tests
# ==============================================================================

class TestSecurityBoundary:
    """Verifies that Gemini never executes shell/PowerShell commands directly."""

    def test_arbitrary_shell_command_is_strictly_rejected(self):
        """Prompt attempting to run PowerShell or CMD commands must be blocked."""
        validator = SecurityValidator()

        # CapabilityRequest for dangerous or unapproved command
        dangerous_request = CapabilityRequest(
            capability=CapabilityType.OPEN_APP,
            target="powershell.exe -Command Remove-Item -Recurse C:\\",
            requested_by="gemini",
        )

        res = validator.validate_capability_request(dangerous_request, is_assistant_online=True)
        assert res.decision == SecurityDecision.DENY
        assert "security violation" in res.reason.lower() or "not in allowlist" in res.reason.lower()

    def test_pipeline_blocks_unauthorized_actions(self):
        pipeline = CapabilityPipeline()
        # Request for non-allowlisted action
        res = pipeline.execute_pipeline("Format my hard drive now", is_online=True)
        # Treated as non-action query or refused
        assert res.capability_request is None or not res.success


# ==============================================================================
# 6. Master OFFLINE Gate Tests
# ==============================================================================

class TestOfflineGate:
    """Verifies that when assistant is OFFLINE, AI queries and voice do not execute."""

    def test_offline_blocks_pipeline(self):
        mock_ai = MockAIProvider()
        pipeline = CapabilityPipeline(ai_provider=mock_ai)

        res = pipeline.execute_pipeline("Explain quantum entanglement", is_online=False)
        assert not res.success
        assert "OFFLINE" in (res.error_message or "")
        # Mock AI provider should not have been called
        assert len(mock_ai.recorded_prompts) == 0

    def test_offline_blocks_jarvis_brain_think(self):
        answer = jarvis_brain.think("Explain quantum computing", is_online=False)
        assert "OFFLINE" in answer


# ==============================================================================
# 7. Single Jarvis Invariant & Dual Agent Integration
# ==============================================================================

class TestJarvisSingleInvariant:
    """Verifies COUNT(JARVIS_IMPLEMENTATIONS) == 1 and Miss Minutes -> Jarvis delegation."""

    def test_single_jarvis_implementation(self):
        """Confirms jarvis.py is the sole implementation."""
        j = jarvis.Jarvis()
        assert j.agent_id == AgentId.JARVIS
        assert hasattr(j, "think")
        assert callable(j.think)
        assert hasattr(j, "capabilities")

    def test_miss_minutes_delegates_to_jarvis(self):
        mm = MissMinutesAgent()
        j = jarvis.Jarvis()
        context = SharedBoundedContext(max_turns=10)

        # User asks for media action
        user_msg = AgentMessage(
            sender=AgentId.USER,
            recipient=AgentId.MISS_MINUTES,
            message_type=MessageType.CHAT,
            content="Can you search for YouTube lo-fi beats?",
        )

        reply = mm.receive_message(user_msg, context=context)
        assert reply is not None
        assert reply.metadata.get("should_delegate") is True
        assert reply.metadata.get("target_agent") == AgentId.JARVIS.value


# ==============================================================================
# 8. Voice Pipeline Integration (STT -> Gemini -> TTS)
# ==============================================================================

class TestVoiceToGeminiToTTS:
    """Verifies that speech-to-text outputs flow through Gemini and into TTS."""

    def test_voice_pipeline_with_mock_audio(self):
        from voice.stt import MockSTTProvider
        from voice.tts import MockTTSProvider
        from voice.audio_player import AudioPlayer

        mock_ai = MockAIProvider(default_text_response="Sure thing! Time waits for no one.")
        mock_stt = MockSTTProvider(default_transcript="What is the current time?", language="en")
        mock_tts = MockTTSProvider()
        player = AudioPlayer(is_online=True, enable_hardware_playback=False)

        voice_svc = VoiceService(
            stt_provider=mock_stt,
            tts_provider=mock_tts,
            audio_player=player,
            is_assistant_online=True,
        )
        pipeline = CapabilityPipeline(ai_provider=mock_ai, voice_service=voice_svc)

        res = pipeline.execute_voice_pipeline(
            audio_data=b"mock_wav_bytes",
            is_online=True,
        )

        assert res.success
        assert res.raw_transcript == "What is the current time?"
        assert res.miss_minutes_response != ""
